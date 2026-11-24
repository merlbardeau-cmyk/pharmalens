"""GLEIF enrichment: LEI, legal-seat country, direct + ultimate parent (company_relation).

Match rule: accept a GLEIF record only if legal_key(GLEIF legalName) == our legal_key (exact, incl. legal form).
Otherwise no LEI (no fuzzy acceptance). Parents not yet in `company` are created as official GLEIF entities.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher  # noqa: E402
from models.db import add_gap, connect, new_id, now, upsert_versioned  # noqa: E402
from resolve.companies import legal_key  # noqa: E402

API = "https://api.gleif.org/api/v1"
CMP = ["name_normalized", "name_raw", "country", "country_basis", "lei", "roles"]


def latin_name(ent) -> str:
    """legal name; for non-Latin scripts the English alternative / transliterated name (brief: transliteration)."""
    name = ent["legalName"]["name"]
    if all(ord(ch) < 0x250 for ch in name):
        return name
    for alt in (ent.get("transliteratedOtherNames") or []) + (ent.get("otherNames") or []):
        if alt.get("language", "").startswith("en") or alt.get("type", "").startswith("AUTO_ASCII") or all(ord(ch) < 0x250 for ch in alt["name"]):
            return alt["name"]
    return name


def company_for_lei(conn, rec, raw_id):
    lei = rec["id"]
    row = conn.execute("SELECT company_id FROM company WHERE lei=%s AND valid_to IS NULL", (lei,)).fetchone()
    if row:
        return row[0]
    ent = rec["attributes"]["entity"]
    key = legal_key(latin_name(ent))
    row = conn.execute("SELECT company_id, name_raw, roles FROM company WHERE name_normalized=%s AND valid_to IS NULL", (key,)).fetchone()
    cid = row[0] if row else new_id(conn)
    upsert_versioned(conn, "company", "company_id", cid, dict(
        name_normalized=key, name_raw=sorted(set((row[1] if row else []) + [ent["legalName"]["name"], latin_name(ent)])),
        country=ent["legalAddress"]["country"], country_basis="GLEIF legal address", lei=lei, roles=row[2] if row else [],
        source_url=f"{API}/lei-records/{lei}", source_name="GLEIF LEI API", retrieved_at=now(), status="official", raw_id=raw_id), CMP)
    return cid


def relation(conn, parent_id, child_id, rtype, url, raw_id):
    if conn.execute("SELECT 1 FROM company_relation WHERE parent_id=%s AND child_id=%s AND relation_type=%s AND valid_to IS NULL",
                    (parent_id, child_id, rtype)).fetchone():
        return
    conn.execute("""INSERT INTO company_relation (parent_id, child_id, relation_type, source_url, source_name, retrieved_at,
                    status, raw_id) VALUES (%s,%s,%s,%s,'GLEIF LEI API',%s,'official',%s)""",
                 (parent_id, child_id, rtype, url, now(), raw_id))


def run(limit=None):
    st = dict(checked=0, matched=0, parents=0, ultimate=0)
    with connect() as conn:
        f = Fetcher(conn, "GLEIF LEI API", raw_dir="gleif")
        todo = conn.execute("""SELECT c.company_id, c.name_normalized, c.name_raw FROM company c
                               LEFT JOIN (SELECT company_id, max(coalesce(n_products, n_apis, 0)) AS w FROM company_role
                                          WHERE valid_to IS NULL GROUP BY 1) r USING (company_id)
                               WHERE c.valid_to IS NULL AND c.lei IS NULL AND c.name_normalized NOT LIKE '%%|-'
                               AND (r.w IS NOT NULL OR 'api_manufacturer'=ANY(c.roles) OR 'fdf_manufacturer'=ANY(c.roles))
                               AND NOT EXISTS (SELECT 1 FROM raw_object ro WHERE ro.url LIKE '%%fuzzycompletions%%'
                                               AND ro.url LIKE '%%' || replace(c.name_raw[1], ' ', '%%') || '%%')
                               ORDER BY r.w DESC NULLS LAST, c.company_id""").fetchall()[:limit]
        for cid, key, names in todo:
            st["checked"] += 1
            r, raw_id = f.get(f"{API}/fuzzycompletions", params={"field": "entity.legalName", "q": names[0]})
            cands = [d["relationships"]["lei-records"]["data"]["id"] for d in r.json().get("data", [])
                     if legal_key(d["attributes"]["value"]) == key] if r.status_code == 200 else []
            if len(cands) != 1:
                continue  # none or ambiguous (same legal name in several countries) -> no LEI, stays for review
            rr, rraw = f.get(f"{API}/lei-records/{cands[0]}")
            if rr.status_code != 200:
                continue
            rec = rr.json()["data"]
            ent = rec["attributes"]["entity"]
            cur = conn.execute("SELECT name_raw, roles FROM company WHERE company_id=%s AND valid_to IS NULL", (cid,)).fetchone()
            upsert_versioned(conn, "company", "company_id", cid, dict(
                name_normalized=key, name_raw=cur[0], country=ent["legalAddress"]["country"], country_basis="GLEIF legal address",
                lei=rec["id"], roles=cur[1], source_url=f"{API}/lei-records/{rec['id']}", source_name="GLEIF LEI API",
                retrieved_at=now(), status="official", raw_id=rraw), CMP)
            st["matched"] += 1
            for kind, rtype in (("direct-parent", "subsidiary"), ("ultimate-parent", "ultimate_parent")):
                rel, relraw = f.get(f"{API}/lei-records/{rec['id']}/{kind}-relationship")
                if rel.status_code != 200 or not rel.json().get("data"):
                    continue
                ra = rel.json()["data"]["attributes"]
                reg = ra["registration"]["status"]
                if reg != "PUBLISHED" or ra["relationship"]["status"] != "ACTIVE":
                    add_gap(conn, "company_structure", "company", cid,
                            f"GLEIF {kind}: Beziehung {reg}/{ra['relationship']['status']}, letzte Aktualisierung "
                            f"{ra['registration']['lastUpdateDate'][:10]} – nicht übernommen (möglicherweise veraltet)",
                            "Handelsregister / Geschäftsbericht / SEC", "GLEIF LEI API")
                    st["stale"] = st.get("stale", 0) + 1
                    continue
                pr, praw = f.get(f"{API}/lei-records/{ra['relationship']['endNode']['id']}")
                if pr.status_code == 200:
                    pid = company_for_lei(conn, pr.json()["data"], praw)
                    relation(conn, pid, cid, rtype, f"{API}/lei-records/{rec['id']}/{kind}-relationship", relraw)
                    st["parents" if kind == "direct-parent" else "ultimate"] += 1
    print("GLEIF", st, flush=True)
    return st


if __name__ == "__main__":
    run(*(int(a) for a in sys.argv[1:]))
