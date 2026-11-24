"""Link nationally listed, centrally authorised products to the EMA product's Annex IIA batch-release sites.

A central authorisation has ONE product information valid in every EEA country, so the Annex IIA sites of the EMA
product apply to the national listing.
  * exact match on EMA procedure number (EMEA/H/C/xxxxxx)  -> status 'official' (same document, exact key)
  * match on brand (first word of name) + shared API          -> status 'derived' (our mapping), rationale stored
Only products WITHOUT own batch-release rows are linked; nothing is overwritten.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.db import connect, norm_text, now  # noqa: E402


def brand(name: str) -> str:
    return norm_text(re.sub(r"[\"®™]", "", name or "")).split(" ")[0]


def run():
    st = dict(candidates=0, exact=0, by_brand=0, no_ema_sites=0, no_match=0)
    with connect() as conn:
        ema = conn.execute("""SELECT p.product_id, p.procedure_no, p.name, array_agg(DISTINCT pa.api_id)
                              FROM product p JOIN product_api pa USING (product_id)
                              WHERE p.valid_to IS NULL AND p.natural_key LIKE 'EMA|%%' GROUP BY 1,2,3""").fetchall()
        by_proc = {e[1]: e for e in ema}
        by_brand = {}
        for e in ema:
            by_brand.setdefault(brand(e[2]), []).append(e)
        nat = conn.execute("""SELECT p.product_id, p.procedure_no, p.name, array_agg(DISTINCT pa.api_id), p.country
                              FROM product p JOIN product_api pa USING (product_id)
                              WHERE p.valid_to IS NULL AND p.country NOT IN ('EU')
                                AND p.source_name NOT LIKE 'EMA Article%%'
                                AND (p.procedure='centralised' OR p.authorisation_no ILIKE 'EU%%' OR p.authorisation_no ILIKE '%%EU/1/%%')
                                AND NOT EXISTS (SELECT 1 FROM product_manufacturer m WHERE m.product_id=p.product_id
                                                AND m.valid_to IS NULL AND m.role='batch_release')
                              GROUP BY 1,2,3,5""").fetchall()
        for pid, proc, name, apis, cc in nat:
            st["candidates"] += 1
            match, status, why = None, None, None
            if proc and proc in by_proc:
                match, status, why = by_proc[proc], "official", f"EMA-Verfahrensnummer {proc} identisch"
            else:
                cands = [e for e in by_brand.get(brand(name), []) if set(e[3]) & set(apis)]
                if len(cands) == 1:
                    match, status = cands[0], "derived"
                    why = f"Markenname '{brand(name)}' + gemeinsamer Wirkstoff (keine Verfahrensnummer in der nationalen Quelle)"
            if not match:
                st["no_match"] += 1
                continue
            sites = conn.execute("""SELECT company_id, manufacturer_raw, site_address_raw, site_country, country_basis, leaflet_url,
                                           evidence_quote, source_url, raw_id FROM product_manufacturer
                                    WHERE product_id=%s AND role='batch_release' AND valid_to IS NULL""", (match[0],)).fetchall()
            if not sites:
                st["no_ema_sites"] += 1
                continue
            for s in sites:
                conn.execute("""INSERT INTO product_manufacturer (product_id, company_id, role, manufacturer_raw, site_address_raw,
                                site_country, country_basis, leaflet_url, evidence_quote, source_url, source_name, retrieved_at,
                                status, raw_id) VALUES (%s,%s,'batch_release',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                             (pid, s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7],
                              f"EMA Annex IIA via {why}"[:200], now(), status, s[8]))
            conn.execute("UPDATE gap SET resolved_at=now() WHERE area='manufacturer' AND entity_ref=%s AND resolved_at IS NULL", (str(pid),))
            st["exact" if status == "official" else "by_brand"] += 1
        print("central link", st)
        return st


if __name__ == "__main__":
    run()
