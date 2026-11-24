"""Phase 3 (pilot): company normalisation + entity resolution.

Rules
  * legal_key = normalised name + canonical legal form. Identical legal_key -> auto merge (score 1.0).
  * Same brand stem, different legal form (Sandoz GmbH vs Sandoz AG) -> different legal entities; logged as 'review'
    candidates for group structure, never merged.
  * Names without legal form ('SANDOZ') stay separate 'name_only' entities.
  * Country: GLEIF legal address (official) > consistent leaflet site country (derived) > NULL.
    Never from the FDA DMF list (holder may be represented by a US agent).
  * Roles from source semantics: DMF/WHO-PQ/Annex-IIA-biological -> api_manufacturer; leaflet batch release ->
    fdf_manufacturer; product MAH -> mah. Importers/MAHs are never promoted to API supplier.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.db import connect, new_id, norm_text, now, upsert_versioned  # noqa: E402

LEGAL_FORMS = [  # (regex on normalised upper name end, canonical)
    (r"PRIVATE LIMITED|PVT\.? LTD|PVT LIMITED", "PVT LTD"), (r"CO\.?,? LTD|COMPANY LIMITED", "CO LTD"),
    (r"LIMITED|LTD", "LTD"), (r"GMBH & CO\.? KG", "GMBH CO KG"), (r"GMBH", "GMBH"), (r"KGAA", "KGAA"),
    (r"AG", "AG"), (r"S\.?A\.?S\.?U?", "SAS"), (r"S\.?A\.?R\.?L\.?", "SARL"), (r"S\.?L\.?U\.?", "SLU"), (r"S\.?L\.?", "SL"),
    (r"S\.?P\.?A\.?", "SPA"), (r"S\.?R\.?L\.?", "SRL"), (r"S\.?A\.?", "SA"), (r"N\.?V\.?", "NV"), (r"B\.?V\.?", "BV"),
    (r"A/S", "AS"), (r"AB", "AB"), (r"OY", "OY"), (r"D\.?\s?D\.?", "DD"), (r"D\.?O\.?O\.?", "DOO"), (r"KFT\.?", "KFT"),
    (r"SP\.? Z\.? ?O\.? ?O\.?", "SPZOO"), (r"S\.?R\.?O\.?", "SRO"), (r"A\.?S\.?", "AS"), (r"LDA\.?", "LDA"),
    (r"PLC", "PLC"), (r"INC\.?", "INC"), (r"LLC", "LLC"), (r"SE", "SE"), (r"EHF\.?|HF\.?", "HF"), (r"AD", "AD"),
    (r"UNLIMITED COMPANY|UC", "UC"), (r"S\.?C\.?S\.?", "SCS"), (r"OOO", "OOO"),
]
_LF = [(re.compile(r"(?:^|[\s,])(" + rx + r")\.?$"), canon) for rx, canon in LEGAL_FORMS]


def normalise(raw: str) -> tuple[str, str | None]:
    """returns (base_name, canonical legal form)"""
    t = norm_text(raw).upper()
    t = re.sub(r"\(.*?\)", " ", t)                      # drop bracketed notes "(PAYS-BAS)"
    t = re.sub(r"[“”\"'´`]", "", t)
    t = re.sub(r"\s+", " ", t.replace(",", " ")).strip(" .-")
    form = None
    for rx, canon in _LF:
        m = rx.search(t)
        if m:
            form = canon
            t = t[:m.start(1)].strip(" ,.-&")
            break
    t = re.sub(r"[^\w& ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t, form


def legal_key(raw: str) -> str:
    base, form = normalise(raw)
    return f"{base}|{form or '-'}"


def collect(conn):
    """raw name -> dict(roles, site_countries, sources)"""
    d = defaultdict(lambda: dict(roles=set(), site_countries=set(), sources=set()))
    for name, src in conn.execute("SELECT DISTINCT mah_raw, source_name FROM product WHERE valid_to IS NULL AND mah_raw IS NOT NULL"):
        d[name]["roles"].add("mah")
        d[name]["sources"].add(src)
    for name, src in conn.execute("SELECT DISTINCT holder_raw, source_name FROM api_certificate WHERE valid_to IS NULL"):
        d[name]["roles"].add("api_manufacturer")
        d[name]["sources"].add(src)
    for name, role, cc, src in conn.execute("SELECT DISTINCT manufacturer_raw, role, site_country, source_name"
                                            " FROM product_manufacturer WHERE valid_to IS NULL"):
        d[name]["roles"].add("api_manufacturer" if role == "api_manufacturer" else "fdf_manufacturer")
        if cc:
            d[name]["site_countries"].add(cc)
        d[name]["sources"].add(src)
    return d


def run():
    with connect() as conn:
        raw = collect(conn)
        groups = defaultdict(list)
        for name in raw:
            groups[legal_key(name)].append(name)
        conn.execute("DELETE FROM entity_merge_log WHERE entity_type='company' AND decision IN ('auto_merged','review')")
        stats = dict(raw_names=len(raw), companies=0, auto_merges=0, name_only=0, review_pairs=0, with_country=0)
        for key, names in groups.items():
            base, form = key.split("|")
            roles = sorted(set().union(*(raw[n]["roles"] for n in names)))
            sites = set().union(*(raw[n]["site_countries"] for n in names))
            row = conn.execute("SELECT company_id, country, country_basis, lei FROM company WHERE name_normalized=%s AND valid_to IS NULL",
                               (key,)).fetchone()
            cid = row[0] if row else new_id(conn)
            country, basis, lei = (row[1], row[2], row[3]) if row and row[2] and row[2].startswith("GLEIF") else (None, None, None)
            if country is None and len(sites) == 1:
                country, basis = next(iter(sites)), "derived: alle Leaflet-Standorte dieser Firma in einem Land"
            upsert_versioned(conn, "company", "company_id", cid, dict(
                name_normalized=key, name_raw=sorted(names), country=country, country_basis=basis, lei=lei, roles=roles,
                source_url="internal:resolve/companies.py", source_name="PharmaLens ER",
                retrieved_at=now(), status="derived" if len(names) > 1 or basis and basis.startswith("derived") else "official"),
                ["name_normalized", "name_raw", "country", "country_basis", "lei", "roles"])
            stats["companies"] += 1
            stats["with_country"] += country is not None
            stats["name_only"] += form == "-"
            for n in names[1:]:
                conn.execute("INSERT INTO entity_merge_log (entity_type, kept_id, merged_id, score, reasons, decision)"
                             " VALUES ('company',%s,%s,1.0,%s,'auto_merged')",
                             (cid, cid, json.dumps(dict(kept=names[0], merged=n, rule="identical name + legal form after normalisation"))))
                stats["auto_merges"] += 1
        # review candidates: same base name, different legal form (potential group members, NOT merged)
        by_base = defaultdict(list)
        for (cid, key) in conn.execute("SELECT company_id, name_normalized FROM company WHERE valid_to IS NULL"):
            by_base[key.split("|")[0]].append((cid, key))
        for base, items in by_base.items():
            for i in range(1, len(items)):
                conn.execute("INSERT INTO entity_merge_log (entity_type, kept_id, merged_id, score, reasons, decision)"
                             " VALUES ('company',%s,%s,0.8,%s,'review')",
                             (items[0][0], items[i][0], json.dumps(dict(a=items[0][1], b=items[i][1],
                                                                        rule="same name, different legal form -> distinct legal entities; check group relation"))))
                stats["review_pairs"] += 1
        # foreign keys back to facts
        conn.execute("""UPDATE product p SET mah_company_id=c.company_id FROM company c
                        WHERE c.valid_to IS NULL AND p.valid_to IS NULL AND p.mah_raw = ANY(c.name_raw)""")
        conn.execute("""UPDATE api_certificate a SET holder_company_id=c.company_id FROM company c
                        WHERE c.valid_to IS NULL AND a.valid_to IS NULL AND a.holder_raw = ANY(c.name_raw)""")
        conn.execute("""UPDATE product_manufacturer m SET company_id=c.company_id FROM company c
                        WHERE c.valid_to IS NULL AND m.valid_to IS NULL AND m.manufacturer_raw = ANY(c.name_raw)""")
        print("ER", stats)
        return stats


if __name__ == "__main__":
    run()
