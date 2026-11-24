"""Company aliases and roles (v2 step 2).

company_alias: every spelling under which a company appears in the registers (MAH field, leaflet manufacturer
section, DMF holder), with how often and in which sources; GLEIF names (incl. non-Latin) and the brand group name.

company_role (all derived from register data, never from outside claims):
  mah               holds marketing authorisations (product.mah_company_id)
  fdf_manufacturer  named as batch-release site in a package leaflet / Annex IIA
  api_manufacturer  US DMF holder (Type II API) or linked API manufacturer
  cdmo              batch-release site for >= 2 MAHs outside its own group (brand group or GLEIF parent).
                    Contract manufacturing is inferred, not confirmed: status 'derived' + rationale + evidence rows.
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.db import connect, norm_text, now  # noqa: E402

SRC = "internal:enrich/company_profile.py"
CDMO_MIN_MAHS = 2


def close_current(conn, table):
    conn.execute(f"UPDATE {table} SET valid_to=now() WHERE valid_to IS NULL")


def groups(conn):
    g = defaultdict(set)
    for parent, child, _ in conn.execute("""SELECT parent_id, child_id, relation_type FROM company_relation WHERE valid_to IS NULL
                                            AND relation_type IN ('brand_group_member','subsidiary','ultimate_parent')""").fetchall():
        g[child].add(parent)
        g[parent].add(parent)
    return g


def same_group(g, a, b):
    if a == b:
        return True
    ga, gb = g.get(a, set()) | {a}, g.get(b, set()) | {b}
    return bool(ga & gb)


def run():
    st = {}
    with connect() as conn:
        ts = now()
        # ---------- aliases
        seen = defaultdict(lambda: [0, set()])
        for cid, raw, src in conn.execute("""
                SELECT mah_company_id, mah_raw, source_name FROM product WHERE valid_to IS NULL AND mah_company_id IS NOT NULL
                UNION ALL SELECT pm.company_id, pm.manufacturer_raw, pm.source_name FROM product_manufacturer pm
                          WHERE pm.valid_to IS NULL AND pm.company_id IS NOT NULL
                UNION ALL SELECT holder_company_id, holder_raw, source_name FROM api_certificate
                          WHERE valid_to IS NULL AND holder_company_id IS NOT NULL""").fetchall():
            raw = (raw or "").strip()
            if not raw or len(raw) > 200:
                continue
            s = seen[(cid, raw)]
            s[0] += 1
            s[1].add(src.split(" via ")[0])
        names = {cid: (nr or [], src) for cid, nr, src in conn.execute(
            "SELECT company_id, name_raw, source_name FROM company WHERE valid_to IS NULL").fetchall()}
        rows = []
        best = {}
        for (cid, raw), (n, srcs) in seen.items():
            if cid in names and (cid not in best or n > best[cid][1]):
                best[cid] = (raw, n)
        for (cid, raw), (n, srcs) in seen.items():
            if cid not in names:
                continue
            kind = "legal_name" if best[cid][0] == raw else "spelling"
            rows.append((cid, raw, kind, n, sorted(srcs), "derived"))
        for cid, (nr, src) in names.items():
            for nm in nr:
                if (cid, nm) in seen or not nm:
                    continue
                if src.startswith("GLEIF"):
                    kind = "transliteration" if re.search(r"[^\x00-ɏ\s]", nm) else "gleif_other_name"
                    rows.append((cid, nm, kind, None, ["GLEIF"], "official"))
        for child, gname in conn.execute("""SELECT r.child_id, g.name_raw[1] FROM company_relation r
                                            JOIN company g ON g.company_id=r.parent_id AND g.valid_to IS NULL
                                            WHERE r.valid_to IS NULL AND r.relation_type='brand_group_member'""").fetchall():
            rows.append((child, gname, "brand_group", None, ["PharmaLens ER"], "derived"))
        close_current(conn, "company_alias")
        dedup = {}
        for cid, al, kind, n, srcs, status in rows:
            k = (cid, norm_text(al), kind)
            if k[1] and k not in dedup:
                dedup[k] = (cid, al, k[1], kind, n, srcs, status)
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO company_alias (company_id, alias, alias_norm, kind, n_observed, seen_in, source_url,
                               source_name, retrieved_at, status) VALUES (%s,%s,%s,%s,%s,%s,%s,'PharmaLens ER',%s,%s)""",
                            [(c, a, an, k, n, s, SRC, ts, stt) for c, a, an, k, n, s, stt in dedup.values()])
        st["aliases"] = len(dedup)

        # ---------- roles
        close_current(conn, "company_role")
        roles = []
        for cid, n_prod, n_api, n_mkt, ev in conn.execute("""
                SELECT p.mah_company_id, count(DISTINCT p.product_id), count(DISTINCT pa.api_id), count(DISTINCT p.country),
                       (array_agg(DISTINCT p.row_id))[1:50]
                FROM product p LEFT JOIN product_api pa ON pa.product_id=p.product_id
                WHERE p.valid_to IS NULL AND p.mah_company_id IS NOT NULL GROUP BY 1""").fetchall():
            roles.append((cid, "mah", n_prod, n_api, n_mkt, f"Zulassungsinhaber für {n_prod} Produkte in {n_mkt} Märkten",
                          ev, "official"))
        for cid, n_prod, n_api, n_mkt, ev in conn.execute("""
                SELECT pm.company_id, count(DISTINCT pm.product_id), count(DISTINCT pa.api_id), count(DISTINCT p.country),
                       (array_agg(DISTINCT pm.row_id))[1:50]
                FROM product_manufacturer pm JOIN product p ON p.product_id=pm.product_id AND p.valid_to IS NULL
                LEFT JOIN product_api pa ON pa.product_id=pm.product_id
                WHERE pm.valid_to IS NULL AND pm.company_id IS NOT NULL AND pm.status='official' GROUP BY 1""").fetchall():
            roles.append((cid, "fdf_manufacturer", n_prod, n_api, n_mkt,
                          f"In Packungsbeilage/Annex IIA als Chargenfreigabe-Standort genannt ({n_prod} Produkte)", ev, "official"))
        for cid, n_api, ev in conn.execute("""
                SELECT holder_company_id, count(DISTINCT api_id), (array_agg(DISTINCT row_id))[1:50] FROM api_certificate
                WHERE valid_to IS NULL AND holder_company_id IS NOT NULL GROUP BY 1""").fetchall():
            roles.append((cid, "api_manufacturer", None, n_api, None, f"Inhaber von US-DMF Typ II für {n_api} Wirkstoffe", ev, "official"))
        # CDMO
        g = groups(conn)
        foreign = defaultdict(lambda: [set(), set(), set(), set()])  # mahs, products, countries, evidence
        apis = defaultdict(set)
        for pm_row, cid, pid, mah, cc in conn.execute("""
                SELECT pm.row_id, pm.company_id, pm.product_id, p.mah_company_id, p.country
                FROM product_manufacturer pm JOIN product p ON p.product_id=pm.product_id AND p.valid_to IS NULL
                WHERE pm.valid_to IS NULL AND pm.status='official' AND pm.company_id IS NOT NULL
                  AND p.mah_company_id IS NOT NULL""").fetchall():
            if same_group(g, cid, mah):
                continue
            f = foreign[cid]
            f[0].add(mah); f[1].add(pid); f[2].add(cc); f[3].add(pm_row)
        pa = defaultdict(set)
        for pid, aid in conn.execute("SELECT product_id, api_id FROM product_api").fetchall():
            pa[pid].add(aid)
        for cid, (mahs, prods, ccs, ev) in foreign.items():
            if len(mahs) < CDMO_MIN_MAHS:
                continue
            n_api = len(set().union(*(pa[p] for p in prods)))
            roles.append((cid, "cdmo", len(prods), n_api, len(ccs),
                          f"Chargenfreigabe für {len(prods)} Produkte von {len(mahs)} konzernfremden Zulassungsinhabern "
                          f"in {len(ccs)} Märkten (Konzern = Markengruppe oder GLEIF-Mutter). Lohnfertigung abgeleitet, nicht bestätigt.",
                          sorted(ev)[:50], "derived"))
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO company_role (company_id, role, n_products, n_apis, n_markets, rationale, evidence_ids,
                               source_url, source_name, retrieved_at, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'PharmaLens ER',%s,%s)""",
                            [(*r[:7], SRC, ts, r[7]) for r in roles])
        st["roles"] = Counter(r[1] for r in roles)
        print("company_profile", st)


if __name__ == "__main__":
    run()
