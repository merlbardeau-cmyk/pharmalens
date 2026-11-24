"""Dashboard export (v2 step 4) -> out/dashboard.json

week sentence, KPIs, new US DMF with potential customers (derived), authorisations per month, API x market heatmap,
top CDMO / MAH, data quality. All numbers are counts of stored rows; nothing is estimated.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graph.export_app import d, dump  # noqa: E402
from models.db import connect  # noqa: E402

TYPE = {"new_dmf": "Neue US-DMF", "new_authorisation": "Neue Zulassung", "shortage": "Lieferengpass", "patent_expiry": "Patentablauf"}


def run(out: Path, today: date | None = None):
    today = today or date.today()
    w7, m30, m24 = today - timedelta(days=7), today - timedelta(days=30), date(today.year - 2, today.month, 1)
    with connect() as c:
        q = lambda sql, *a: c.execute(sql, a).fetchall()  # noqa: E731
        inn = dict(q("SELECT api_id, inn FROM api WHERE valid_to IS NULL"))
        name = dict(q("SELECT company_id, name_raw[1] FROM company WHERE valid_to IS NULL"))
        cnt = {t: dict(week=0, month=0, year=0) for t in TYPE}
        for t, dt in q("SELECT signal_type, signal_date FROM signal WHERE valid_to IS NULL"):
            if dt and dt <= today:
                cnt[t]["year"] += 1
                cnt[t]["month"] += dt >= m30
                cnt[t]["week"] += dt >= w7
        cnt["patent_expiry"]["next24m"] = q("SELECT count(*) FROM signal WHERE valid_to IS NULL AND signal_type='patent_expiry'")[0][0]
        cnt["shortage"]["open"] = q("SELECT count(*) FROM signal WHERE valid_to IS NULL AND signal_type='shortage'")[0][0]
        parts = []
        if cnt["new_authorisation"]["week"]:
            parts.append(f"{cnt['new_authorisation']['week']} neue Zulassungen")
        if cnt["new_dmf"]["month"]:
            parts.append(f"{cnt['new_dmf']['month']} neue US-DMF in 30 Tagen")
        if cnt["shortage"]["open"]:
            parts.append(f"{cnt['shortage']['open']} offene Lieferengpässe")
        sentence = ("Letzte 7 Tage: " + ", ".join(parts) + ".") if parts else "Keine neuen Signale in den letzten 7 Tagen."

        # new DMF + potential customers
        pcs = defaultdict(list)
        for aid, cid, score, reasons, npd, ncc in q("""SELECT api_id, company_id, score, reasons, n_products, n_countries
                                                      FROM potential_customer WHERE valid_to IS NULL ORDER BY score DESC"""):
            pcs[aid].append(dict(id=cid, name=name.get(cid), score=float(score), reasons=reasons, products=npd, markets=ncc))
        from enrich.company_profile import groups, same_group
        g = groups(c)
        ext = lambda aid, h: [x for x in pcs.get(aid, []) if not same_group(g, x["id"], h)]  # noqa: E731
        dmf = [dict(date=d(dt), api=inn.get(aid), holder=name.get(cid), holder_id=cid, no=(de or {}).get("number"), url=url,
                    customers=ext(aid, cid)[:5], n_customers=len(ext(aid, cid)))
               for dt, aid, cid, de, url in q("""SELECT signal_date, api_id, company_id, detail, source_url FROM signal
                                                 WHERE valid_to IS NULL AND signal_type='new_dmf' ORDER BY signal_date DESC""")]

        # authorisations per month and market
        months = defaultdict(lambda: defaultdict(int))
        for m, cc, n in q("""SELECT to_char(auth_date,'YYYY-MM'), country, count(*) FROM product WHERE valid_to IS NULL
                             AND auth_date >= %s AND auth_date <= %s GROUP BY 1,2""", m24, today):
            months[m][cc] += n
        auth = dict(months=sorted(months), by_cc={m: dict(v) for m, v in months.items()})

        # heatmap pilot APIs x markets
        heat = q("""SELECT a.inn, p.country, count(DISTINCT p.product_id) FROM product p JOIN product_api pa ON pa.product_id=p.product_id
                    JOIN api a ON a.api_id=pa.api_id AND a.valid_to IS NULL AND a.parent_api_id IS NULL
                    WHERE p.valid_to IS NULL GROUP BY 1,2""")
        apis = sorted({h[0] for h in heat}, key=lambda a: -sum(h[2] for h in heat if h[0] == a))
        ccs = sorted({h[1] for h in heat}, key=lambda x: -sum(h[2] for h in heat if h[1] == x))

        top = lambda role: [dict(id=cid, name=name.get(cid), products=npd, markets=nmk, status=st)  # noqa: E731
                            for cid, npd, nmk, st in q("""SELECT company_id, n_products, n_markets, status FROM company_role
                                                         WHERE valid_to IS NULL AND role=%s ORDER BY n_products DESC LIMIT 10""", role)]

        # data quality per market
        quality = [dict(cc=cc, products=n, auth_date=nd, manufacturer=nm)
                   for cc, n, nd, nm in q("""SELECT p.country, count(*), count(p.auth_date),
                                                    count(*) FILTER (WHERE EXISTS (SELECT 1 FROM product_manufacturer pm
                                                        WHERE pm.product_id=p.product_id AND pm.valid_to IS NULL))
                                             FROM product p WHERE p.valid_to IS NULL GROUP BY 1 ORDER BY 2 DESC""")]
        status_mix = defaultdict(int)
        for t in ("product", "product_manufacturer", "api_certificate", "company", "company_relation", "company_role", "supply_link", "signal"):
            for st, n in q(f"SELECT status::text, count(*) FROM {t} WHERE valid_to IS NULL GROUP BY 1"):
                status_mix[st] += n
        gaps = q("SELECT area, count(*) FROM gap WHERE resolved_at IS NULL GROUP BY 1 ORDER BY 2 DESC")
        recent = [dict(type=t, label=TYPE[t], date=d(dt), title=ti, api=inn.get(aid), company=name.get(cid), company_id=cid, cc=cc, url=url, status=st)
                  for t, dt, ti, aid, cid, cc, url, st in q("""SELECT signal_type, signal_date, title, api_id, company_id, country, source_url, status::text
                       FROM signal WHERE valid_to IS NULL AND signal_date <= %s ORDER BY signal_date DESC, signal_id LIMIT 60""", today)]
        kpi = dict(products=q("SELECT count(*) FROM product WHERE valid_to IS NULL")[0][0],
                   markets=q("SELECT count(DISTINCT country) FROM product WHERE valid_to IS NULL")[0][0],
                   releases=q("SELECT count(DISTINCT product_id) FROM product_manufacturer WHERE valid_to IS NULL")[0][0],
                   cdmo=q("SELECT count(*) FROM company_role WHERE valid_to IS NULL AND role='cdmo'")[0][0])
        dump(dict(generated=today.isoformat(), sentence=sentence, counts=cnt, kpi=kpi, dmf=dmf, auth=auth,
                  heat=dict(apis=apis, ccs=ccs, cells=[[apis.index(a), ccs.index(cc), n] for a, cc, n in heat]),
                  top_cdmo=top("cdmo"), top_mah=top("mah"), quality=quality, status_mix=dict(status_mix),
                  gaps=[dict(area=a, n=n) for a, n in gaps], recent=recent), out / "dashboard.json")
        print("dashboard", sentence, kpi)


if __name__ == "__main__":
    run(Path(sys.argv[1]))
