"""Signals + potential customers (v2 step 4).

signal (all official, taken 1:1 from a register date):
  new_dmf            US DMF Type II submitted in the last 12 months (FDA DMF list)        -- substitute for new_cep (EDQM licence open)
  new_authorisation  product authorisation date in the last 12 months (national registers, EMA)
  shortage           shortage events (EMA / AEMPS)
  patent_expiry      Orange Book patent expiring in the next 24 months
new_cep and gmp_noncompliance stay gaps (EDQM licence, EudraGMDP returns no results).

potential_customer (status derived): for every API with a new US DMF, the marketing-authorisation holders that sell
finished products with that API in the covered markets, outside the DMF holder's group. Score = products + 3 * markets.
Selling the API is a reason to talk, not proof of demand.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enrich.company_profile import groups, same_group  # noqa: E402
from models.db import add_gap, connect, now  # noqa: E402

SRC = "internal:graph/signals.py"


def run(today: date | None = None):
    today = today or date.today()
    y1, y2 = today - timedelta(days=365), today + timedelta(days=730)
    st = defaultdict(int)
    with connect() as c:
        ts = now()
        c.execute("UPDATE signal SET valid_to=now() WHERE valid_to IS NULL")
        c.execute("UPDATE potential_customer SET valid_to=now() WHERE valid_to IS NULL")
        rows = []
        for rid, aid, cid, no, d, url, src in c.execute("""
                SELECT row_id, api_id, holder_company_id, number, issue_date, source_url, source_name FROM api_certificate
                WHERE valid_to IS NULL AND cert_type='US_DMF' AND issue_date >= %s""", (y1,)).fetchall():
            rows.append(("new_dmf", d, aid, cid, None, None, f"Neue US-DMF {no}", dict(number=no), [rid], url, src))
        for rid, pid, aid, cid, cc, d, name, url, src in c.execute("""
                SELECT p.row_id, p.product_id, min(pa.api_id), p.mah_company_id, p.country, p.auth_date, p.name, p.source_url, p.source_name
                FROM product p LEFT JOIN product_api pa ON pa.product_id=p.product_id
                WHERE p.valid_to IS NULL AND p.auth_date >= %s AND p.auth_date <= %s
                GROUP BY 1,2,4,5,6,7,8,9""", (y1, today)).fetchall():
            rows.append(("new_authorisation", d, aid, cid, pid, cc, f"Neue Zulassung {name}", dict(source_field="auth_date"), [rid], url, src))
        for rid, aid, d, de, url, src in c.execute("""
                SELECT row_id, entity_ref, event_date, detail, source_url, source_name FROM event
                WHERE valid_to IS NULL AND event_type='shortage' AND entity_type='api'""").fetchall():
            de = {k: v for k, v in (de or {}).items() if v not in ("nan", None, "")}
            if de.get("active") is False or "resolved" in str(de.get("state", "")).lower():
                continue  # only open shortages are signals
            rows.append(("shortage", d, aid, None, None, (de.get("country") or "")[:2] or None,
                         f"Lieferengpass {de.get('product', '')}".strip(), de, [rid], url, src))
        for rid, aid, no, d, ptype, url, src in c.execute("""
                SELECT row_id, api_id, number, expiry, patent_type, source_url, source_name FROM patent
                WHERE valid_to IS NULL AND expiry BETWEEN %s AND %s""", (today, y2)).fetchall():
            rows.append(("patent_expiry", d, aid, None, None, "US", f"US-Patent {no} läuft ab", dict(number=no, type=ptype), [rid], url, src))
        with c.cursor() as cur:
            cur.executemany("""INSERT INTO signal (signal_type, signal_date, api_id, company_id, product_id, country, title, detail,
                               evidence_ids, source_url, source_name, retrieved_at, status)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'official')""",
                            [(t, d, a, co, p, cc, ti, json.dumps(de, default=str), ev, u, s, ts) for t, d, a, co, p, cc, ti, de, ev, u, s in rows])
        for r in rows:
            st[r[0]] += 1
        for t, why in (("new_cep", "EDQM-CEP-Datenbank: Lizenzanfrage offen, neue CEPs nicht abrufbar"),
                       ("gmp_noncompliance", "EudraGMDP liefert für automatisierte Abfragen keine Treffer")):
            add_gap(c, "signal", "signal_type", t, why, None, "graph/signals.py")

        # potential customers for APIs with a new DMF
        g = groups(c)
        holders = defaultdict(set)
        for aid, cid in c.execute("SELECT api_id, company_id FROM signal WHERE valid_to IS NULL AND signal_type='new_dmf'").fetchall():
            holders[aid].add(cid)
        pcs = []
        for aid, hs in holders.items():
            agg = defaultdict(lambda: [set(), set(), []])
            for rid, pid, mah, cc in c.execute("""SELECT p.row_id, p.product_id, p.mah_company_id, p.country FROM product p
                                                  JOIN product_api pa ON pa.product_id=p.product_id
                                                  WHERE p.valid_to IS NULL AND pa.api_id=%s AND p.mah_company_id IS NOT NULL""", (aid,)).fetchall():
                if any(h and same_group(g, mah, h) for h in hs):
                    continue
                a = agg[mah]
                a[0].add(pid); a[1].add(cc); a[2].append(rid)
            for mah, (prods, ccs, ev) in agg.items():
                score = len(prods) + 3 * len(ccs)
                pcs.append((aid, mah, score, [f"{len(prods)} Fertigprodukte mit diesem Wirkstoff", f"zugelassen in {len(ccs)} Märkten: {', '.join(sorted(ccs))}",
                                              "nicht im Konzern des DMF-Inhabers"], ev[:50], len(prods), len(ccs)))
        with c.cursor() as cur:
            cur.executemany("""INSERT INTO potential_customer (api_id, company_id, score, reasons, evidence_ids, n_products, n_countries,
                               source_url, source_name, retrieved_at, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'PharmaLens',%s,'derived')""",
                            [(*p, SRC, ts) for p in pcs])
        st["potential_customers"] = len(pcs)
        print("signals", dict(st))


if __name__ == "__main__":
    run()
