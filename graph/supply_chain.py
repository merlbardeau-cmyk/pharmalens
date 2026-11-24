"""Phase 7 (pilot): supply_link from primary-source co-occurrence only.

confirmed  : both ends named in the same primary document
             - leaflet / Annex IIA: batch-release site (company) -> product (country, MAH)
             - Annex IIA biological active substance manufacturer -> product (API supplier, confirmed)
derived    : not produced in the pilot (needs EU-DMF hints / PARs)
hypothesis : never produced automatically
API -> FDF links for chemical generics without a primary document stay open and are written to `gap`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.db import add_gap, connect, now  # noqa: E402


def run():
    with connect() as conn:
        conn.execute("DELETE FROM supply_link WHERE status='official'")
        conn.execute("DELETE FROM evidence WHERE kind='leaflet_manufacturer'")
        rows = conn.execute("""SELECT pm.row_id, pm.product_id, pm.company_id, pm.role, pm.evidence_quote, pm.source_url,
                                      pm.source_name, pm.retrieved_at, pm.raw_id
                               FROM product_manufacturer pm WHERE pm.valid_to IS NULL AND pm.company_id IS NOT NULL""").fetchall()
        n = {"api_manufacturer": 0, "batch_release": 0}
        for rid, pid, cid, role, quote, url, src, ts, raw in rows:
            ev = conn.execute("""INSERT INTO evidence (kind, entity_type, entity_ref, evidence_quote, source_url, source_name,
                                 retrieved_at, status, raw_id) VALUES ('leaflet_manufacturer','product_manufacturer',%s,%s,%s,%s,%s,
                                 'official',%s) RETURNING evidence_id""", (rid, quote, url, src, ts, raw)).fetchone()[0]
            ltype = "api_manufacturer_to_product" if role == "api_manufacturer" else "fdf_site_to_product"
            conn.execute("""INSERT INTO supply_link (from_type, from_id, to_type, to_id, link_type, confidence, rationale,
                            evidence_ids, source_url, source_name, retrieved_at, status)
                            VALUES ('company',%s,'product',%s,%s,'confirmed',%s,%s,%s,%s,%s,'official')""",
                         (cid, pid, ltype, "Hersteller und Produkt im selben Primärdokument genannt", [ev], url, src, now()))
            n[role] = n.get(role, 0) + 1
        # open API -> FDF links (chemical APIs without primary evidence)
        for aid, inn in conn.execute("""SELECT a.api_id, a.inn FROM api a WHERE a.parent_api_id IS NULL AND a.valid_to IS NULL
                                        AND NOT EXISTS (SELECT 1 FROM supply_link s JOIN product_api pa ON pa.product_id=s.to_id
                                                        WHERE pa.api_id=a.api_id AND s.link_type='api_manufacturer_to_product')""").fetchall():
            add_gap(conn, "supply_chain", "api", inn,
                    "API-Lieferant der Fertigprodukte nicht in Primärquelle belegt (für Generika i. d. R. vertraulich; ASMF nicht öffentlich)",
                    "Public Assessment Reports (HMA MRI), EudraGMDP, CEP-Lizenz", "PharmaLens graph")
        print("supply_link confirmed:", n)


if __name__ == "__main__":
    run()
