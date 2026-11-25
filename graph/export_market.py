"""Market 360 export: one file per country (out/mkt/<CC>.json) with the country view and a drill-down per pilot API.

Volumes and prices are only exported where a public source exists; every block names its metric (packs, EUR amount,
number of products) and its source. Missing blocks are exported as gaps with the reason - never estimated.
"""
from __future__ import annotations

import re
import shutil
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enrich.company_profile import groups, same_group  # noqa: E402
from graph.export_app import COUNTRY_NAME, d, dump, slug  # noqa: E402
from graph.i18n_en import en  # noqa: E402
from models.db import connect  # noqa: E402

EEA = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
       "PL", "PT", "RO", "SK", "SI", "ES", "SE", "IS", "LI", "NO", "EU", "XI"}
AUTHORITY = {"FR": "ANSM, HAS/CEPS (prices), Assurance Maladie (volumes)", "ES": "AEMPS, Ministerio de Sanidad (prices)",
             "DK": "Lægemiddelstyrelsen (DKMA), Sundhedsdatastyrelsen (prices, Medstat)", "NL": "CBG-MEB", "AT": "BASG",
             "IT": "AIFA", "CH": "Swissmedic", "US": "FDA", "DE": "BfArM", "EU": "EMA / European Commission"}
MISSING = {  # what a country lacks and which public source would provide it
    "volume": {"ES": "No public dispensing volume per pack (Ministerio de Sanidad publishes aggregated billing only)",
               "DK": "Medstat volume only as an interactive application (Sundhedsdatabanken), no file for automated use",
               "_": "No public volume source connected for this country"},
    "price": {"_": "No public price list connected for this country"},
}


def ratio(a, b):
    return round(100 * a / b) if b else 0


def run(out: Path, today: date | None = None):
    today = today or date.today()
    y1 = today - timedelta(days=365)
    shutil.rmtree(out / "mkt", ignore_errors=True)
    (out / "mkt").mkdir(parents=True, exist_ok=True)
    with connect() as c:
        q = lambda sql, *a: c.execute(sql, a).fetchall()  # noqa: E731
        g = groups(c)
        inn = dict(q("SELECT api_id, inn FROM api WHERE valid_to IS NULL AND parent_api_id IS NULL"))
        cname = dict(q("SELECT company_id, name_raw[1] FROM company WHERE valid_to IS NULL"))
        ccountry = dict(q("SELECT company_id, country FROM company WHERE valid_to IS NULL"))
        papi = defaultdict(set)
        for pid, aid in q("SELECT product_id, api_id FROM product_api"):
            papi[pid].add(aid)
        syn = defaultdict(set)
        for aid, s in q("SELECT api_id, lower(synonym) FROM api_synonym WHERE valid_to IS NULL"):
            syn[aid].add(s)
        dmf_holders = defaultdict(list)
        for aid, cid, no, dt, url in q("""SELECT api_id, holder_company_id, number, issue_date, source_url FROM api_certificate
                                         WHERE valid_to IS NULL AND cert_status='active'"""):
            dmf_holders[aid].append(dict(id=cid, name=cname.get(cid), no=no, date=d(dt), url=url, status="official"))
        pat = defaultdict(list)
        for aid, no, typ, exp, url in q("SELECT api_id, number, patent_type, expiry, source_url FROM patent WHERE valid_to IS NULL ORDER BY expiry DESC"):
            pat[aid].append(dict(no=no, type=typ, exp=d(exp), url=url))
        sources = defaultdict(list)
        for name, jur, light, cat, reason, url in q("SELECT name, jurisdiction, traffic_light, category, traffic_reason, coalesce(probe_url, base_url) FROM source"):
            sources[jur].append(dict(name=name, light=light, cat=cat, reason=en(reason), url=url))
        markets = [r[0] for r in q("SELECT DISTINCT country FROM product WHERE valid_to IS NULL AND country IS NOT NULL")]
        index = []
        for cc in sorted(markets):
            P = {r[0]: dict(pid=r[0], name=r[1], mah_id=r[2], mah=cname.get(r[2]) or r[3], no=r[4], strength=r[5], form=r[6], status=r[7],
                            vet=r[8], date=d(r[9]), subst=r[10], src=r[11], st=r[12], leaf=r[13], proc=r[14], apis=sorted(papi.get(r[0], ())))
                 for r in q("""SELECT product_id, name, mah_company_id, mah_raw, authorisation_no, strength, form, product_status, is_veterinary,
                               auth_date, substances_raw, source_url, status, leaflet_url, procedure FROM product WHERE valid_to IS NULL AND country=%s""", cc)}
            if not P:
                continue
            # manufacturers per product
            mf = defaultdict(list)
            for pid, cid, raw, scc, qt, url, st in q("""SELECT pm.product_id, pm.company_id, pm.manufacturer_raw, pm.site_country, pm.evidence_quote,
                    pm.leaflet_url, pm.status FROM product_manufacturer pm JOIN product p ON p.product_id=pm.product_id AND p.valid_to IS NULL
                    WHERE pm.valid_to IS NULL AND pm.role='batch_release' AND p.country=%s""", cc):
                mf[pid].append(dict(id=cid, name=cname.get(cid) or raw, cc=scc, quote=qt, url=url, st=st))
            # prices (latest per pack and type) and history
            price = defaultdict(list)
            hist = defaultdict(lambda: defaultdict(list))
            for pid, aid, pack, v, cur, ptype, u, nv, pdate, code, rr, url, src in q("""
                    SELECT product_id, api_id, pack_text, value, currency, price_type, units_per_pack, normalized_value, price_date, pack_code,
                           reimbursement_rate, source_url, source_name FROM price WHERE valid_to IS NULL AND country=%s ORDER BY price_date""", cc):
                aids = papi.get(pid, set()) | ({aid} if aid else set())
                rec = dict(pack=pack, value=float(v), cur=cur, type=ptype, units=u, per_unit=float(nv) if nv is not None else None,
                           date=d(pdate), code=code, reimb=rr, url=url, src=src)
                if ptype.startswith("consumer price") and pdate:
                    for a in aids:
                        if nv is not None:
                            hist[a][d(pdate)].append(float(nv))
                key = pid or ("api", tuple(sorted(aids)), code)
                price[key] = [x for x in price[key] if not (x["type"] == ptype and x["code"] == code)] + [rec]
            # generic status
            gen = dict(q("""SELECT pg.product_id, pg.generic_type FROM product_generic pg JOIN product p ON p.product_id=pg.product_id
                            AND p.valid_to IS NULL WHERE pg.valid_to IS NULL AND p.country=%s""", cc))
            # volume
            vol = defaultdict(lambda: defaultdict(float))
            vol_meta = None
            for pid, metric, unit, period, v, url, src in q("""SELECT product_id, metric, unit, period, value, source_url, source_name FROM market_metric
                                                             WHERE valid_to IS NULL AND country=%s""", cc):
                vol_meta = vol_meta or dict(period=period, url=url, src=src)
                if pid:
                    vol[pid][metric] += float(v)
            vol_total = defaultdict(float)
            for _, metric, _, _, v, _, _ in q("SELECT product_id, metric, unit, period, value, source_url, source_name FROM market_metric WHERE valid_to IS NULL AND country=%s", cc):
                vol_total[metric] += float(v)
            # shortages
            shorts = [dict(date=d(dt), api=inn.get(ref) if et == "api" else None, product=(de or {}).get("product"), state=(de or {}).get("state"),
                           active=(de or {}).get("active") is not False and "resol" not in str((de or {}).get("state", "")).lower(),
                           reporter=(de or {}).get("reporter"), domain=(de or {}).get("domain"), url=url, st=st)
                      for dt, et, ref, de, url, st in q("""SELECT event_date, entity_type, entity_ref, detail, source_url, status FROM event
                          WHERE valid_to IS NULL AND event_type='shortage' AND detail->>'country'=%s ORDER BY event_date DESC NULLS LAST""", cc)]
            tenders = [dict(date=d(dt), api=inn.get(aid), buyer=b, winner=w, value=float(v) if v is not None else None, cur=cu, id=nid, url=url)
                       for aid, b, w, v, cu, dt, nid, url in q("""SELECT api_id, buyer, winner_raw, value, currency, award_date, notice_id, source_url
                                                               FROM tender WHERE valid_to IS NULL AND country=%s ORDER BY award_date DESC""", cc)]
            # ---------- aggregates
            prods = list(P.values())
            human = [p for p in prods if not p["vet"]]
            mahs = Counter(p["mah"] for p in prods if p["mah"])
            with_mf = [p for p in prods if mf.get(p["pid"])]
            new12 = [p for p in prods if p["date"] and p["date"] >= d(y1)]
            months = Counter(p["date"][:7] for p in prods if p["date"] and p["date"] >= d(today - timedelta(days=730)))
            has_vol = bool(vol_total)
            has_price = bool(price)
            # largest markets (substances): volume where available, else number of products
            def subst_key(p):
                if p["apis"]:
                    return " + ".join(sorted(inn.get(a, "") for a in p["apis"]))
                parts = [re.sub(r"\s+\d[\d.,]*\s*(mg|g|µg|microgrammes?|ui|u|ml|%|mmol|mg/ml).*$", "", x.strip().lower()) for x in (p["subst"] or "").split("|")]
                parts = sorted({re.sub(r"\s*\(.*?\)\s*", " ", x).strip() for x in parts if x.strip()})
                return " + ".join(parts)[:80] or None
            agg = defaultdict(lambda: dict(products=0, packs=0.0, amount=0.0, api_slug=None))
            for p in prods:
                k = subst_key(p)
                if not k:
                    continue
                a = agg[k]
                a["products"] += 1
                a["packs"] += vol[p["pid"]].get("reimbursed_packs", 0)
                a["amount"] += vol[p["pid"]].get("reimbursed_amount", 0)
                if len(p["apis"]) == 1:
                    a["api_slug"] = slug(inn.get(p["apis"][0], ""))
            metric = "reimbursed_amount" if has_vol else "products"
            top_subst = sorted(([k, v] for k, v in agg.items()), key=lambda x: -(x[1]["amount"] if has_vol else x[1]["products"]))[:25]
            # companies
            mah_vol = defaultdict(float)
            for p in prods:
                if p["mah"]:
                    mah_vol[p["mah"]] += vol[p["pid"]].get("reimbursed_amount", 0)
            mah_ids = {p["mah"]: p["mah_id"] for p in prods if p["mah"]}
            top_mah = [dict(name=m, id=mah_ids.get(m), products=n, amount=round(mah_vol.get(m, 0)) if has_vol else None) for m, n in mahs.most_common(20)]
            if has_vol:
                top_mah_vol = [dict(name=m, id=mah_ids.get(m), amount=round(v), products=mahs[m]) for m, v in sorted(mah_vol.items(), key=lambda x: -x[1])[:20]]
            else:
                top_mah_vol = []
            # supply: batch-release site country group and flows
            site_grp = Counter()
            sites, site_label = Counter(), {}
            flows = Counter()
            for p in prods:
                for m in mf.get(p["pid"], []):
                    grp = "Domestic" if m["cc"] == cc else ("EU/EEA" if m["cc"] in EEA else ("Third country" if m["cc"] else "Unknown"))
                    site_grp[grp] += 1
                    sites[(re.sub(r"[^a-z0-9]+", " ", (m["name"] or "").lower()).strip(), m["cc"])] += 1
                    site_label.setdefault((re.sub(r"[^a-z0-9]+", " ", (m["name"] or "").lower()).strip(), m["cc"]), (m["name"], m["id"]))
                    flows[(m["cc"] or "?", m["name"], p["mah"] or "?")] += 1
            # ---------- API drill-down
            api_detail = {}
            for aid in sorted({a for p in prods for a in p["apis"]}):
                ap = [p for p in prods if aid in p["apis"]]
                if not ap:
                    continue
                rows = []
                for p in ap:
                    pr = price.get(p["pid"], [])
                    rows.append(dict(pid=p["pid"], name=p["name"], strength=p["strength"], form=p["form"], mah=p["mah"], mah_id=p["mah_id"], no=p["no"],
                                     status=p["status"], date=p["date"], st=p["st"], src=p["src"], leaf=p["leaf"],
                                     manufacturers=mf.get(p["pid"], [])[:4], prices=pr[:6], generic=gen.get(p["pid"]),
                                     packs=round(vol[p["pid"]]["reimbursed_packs"]) if has_vol and "reimbursed_packs" in vol.get(p["pid"], {}) else None,
                                     amount=round(vol[p["pid"]]["reimbursed_amount"]) if has_vol and "reimbursed_amount" in vol.get(p["pid"], {}) else None,
                                     shortage=any(s["active"] and s["api"] == inn.get(aid) for s in shorts)))
                if cc == "DK":  # DK prices are linked to the API, not always to a product
                    api_prices = [x for k, v in price.items() if isinstance(k, tuple) and aid in k[1] for x in v]
                else:
                    api_prices = []
                share_metric = "reimbursed_amount" if has_vol and any(r["amount"] for r in rows) else "products"
                sh = defaultdict(float)
                for r in rows:
                    sh[r["mah"] or "?"] += (r["amount"] or 0) if share_metric == "reimbursed_amount" else 1
                tot = sum(sh.values()) or 1
                shares = [dict(mah=m, value=round(v), share=round(100 * v / tot, 1)) for m, v in sorted(sh.items(), key=lambda x: -x[1])]
                # price comparison per unit (consumer/public prices)
                retail = lambda t: not re.search(r"purchase|reference", t)  # noqa: E731  one price type per pack: public/consumer price
                pts = [(r["name"], x["per_unit"], x["type"], x["cur"]) for r in rows for x in r["prices"] if x["per_unit"] is not None and retail(x["type"])]
                pts += [(x["pack"], x["per_unit"], x["type"], x["cur"]) for x in api_prices if x["per_unit"] is not None and retail(x["type"])]
                history = sorted(((dt, round(statistics.median(v), 3)) for dt, v in hist.get(aid, {}).items()), key=lambda x: x[0])
                # potential customers in this country (derived)
                active_short = any(s["active"] and s["api"] == inn.get(aid) for s in shorts)
                soon = [x for x in pat[aid] if x["exp"] and d(today) <= x["exp"] <= d(today + timedelta(days=730))]
                few = 0 < len(dmf_holders[aid]) <= 5
                cust = defaultdict(lambda: dict(products=0, amount=0.0, reasons=[]))
                for r in rows:
                    if not r["mah_id"]:
                        continue
                    x = cust[r["mah_id"]]
                    x["products"] += 1
                    x["amount"] += r["amount"] or 0
                customers = []
                for mid, x in cust.items():
                    score = x["products"] * 3 + (x["amount"] / 1e5 if has_vol else 0) + (15 if active_short else 0) + (10 if soon else 0) + (10 if few else 0)
                    why = [f"{x['products']} products of this API in {COUNTRY_NAME.get(cc, cc)}"]
                    if has_vol and x["amount"]:
                        why.append(f"EUR {round(x['amount']):,} reimbursed in {vol_meta['period']} (Open Medic)")
                    if active_short:
                        why.append("open shortage for this API in this country")
                    if soon:
                        why.append(f"US patent expires {soon[-1]['exp']}")
                    if few:
                        why.append(f"only {len(dmf_holders[aid])} active US DMF holders")
                    customers.append(dict(id=mid, name=cname.get(mid), score=round(score, 1), reasons=why, status="derived"))
                customers.sort(key=lambda x: -x["score"])
                f2 = Counter((m["cc"] or "?", m["name"], r["mah"] or "?") for r in rows for m in r["manufacturers"])
                n_gen = sum(1 for r in rows if r["generic"] == "generic")
                n_ref = sum(1 for r in rows if r["generic"] == "reference")
                api_detail[slug(inn.get(aid, str(aid)))] = dict(
                    api=inn.get(aid), slug=slug(inn.get(aid, "")), synonyms=sorted(syn.get(aid, ()))[:80], products=rows, api_prices=api_prices[-200:],
                    share_metric=share_metric, shares=shares[:15], price_points=pts[:400], history=history, history_metric="median consumer price per unit across all packs listed on that date (DKK)" if history else None,
                    patents=pat[aid][:10], customers=customers[:60], api_sources=dmf_holders[aid], flows=[[a, b, m, n] for (a, b, m), n in f2.most_common(60)],
                    summary=(f"{inn.get(aid, '').capitalize()} in {COUNTRY_NAME.get(cc, cc)}: {len(rows)} products from {len({r['mah'] for r in rows})} authorisation holders; "
                             f"{sum(1 for r in rows if r['manufacturers'])} with a batch-release site from the leaflet; "
                             + (f"{n_gen} generics and {n_ref} reference products (register flag); " if n_gen or n_ref else "")
                             + (f"EUR {sum(r['amount'] or 0 for r in rows):,.0f} reimbursed in {vol_meta['period']}; " if has_vol else "no public volume; ")
                             + f"{len(dmf_holders[aid])} active US DMF holders as possible API sources."),
                    kpi=dict(products=len(rows), mahs=len({r["mah"] for r in rows}), with_mf=sum(1 for r in rows if r["manufacturers"]),
                             packs=sum(r["packs"] or 0 for r in rows) if has_vol else None, amount=sum(r["amount"] or 0 for r in rows) if has_vol else None,
                             shortage=active_short, generics=n_gen, references=n_ref, api_sources=len(dmf_holders[aid])))
            gaps = [dict(area=a, reason=en(r), where=w, n=n) for a, r, w, n in q("""SELECT area, reason, min(where_obtainable), count(*) FROM gap
                    WHERE resolved_at IS NULL AND (entity_ref=%s OR entity_ref IN (SELECT product_id::text FROM product WHERE valid_to IS NULL AND country=%s))
                    GROUP BY 1,2 ORDER BY 4 DESC LIMIT 40""", cc, cc)]
            if not has_vol:
                gaps.insert(0, dict(area="Volume", reason=MISSING["volume"].get(cc, MISSING["volume"]["_"]), where=None, n=None))
            if not has_price:
                gaps.insert(0, dict(area="Prices", reason=MISSING["price"]["_"], where=None, n=None))
            if not tenders:
                gaps.append(dict(area="Tenders", reason="No TED award notice for the pilot APIs with a buyer in this country; national purchasing groups not connected", where=None, n=None))
            if cc == "FR":
                gaps.append(dict(area="Tenders", reason="French hospital purchasing groups (UniHA, Resah, AGEPS) do not publish award data as open files", where=None, n=None))
            has_short_src = any(x["cat"] == "shortage" and x["light"] != "red" for x in sources.get(cc, []))
            if not has_short_src:
                gaps.insert(0, dict(area="Shortages", reason="No national shortage register connected for this country", where=None, n=None))
            if not any(p["date"] for p in prods):
                gaps.insert(0, dict(area="Authorisation date", reason="The register export used provides no authorisation date", where=None, n=None))
            src_list = sources.get(cc, []) + ([s for s in sources.get("EU", []) if s["cat"] in ("approval_eu", "shortage")] if cc in EEA else [])
            summary = (f"{COUNTRY_NAME.get(cc, cc)}: {len(prods):,} authorised products ({len(prods) - len(human):,} veterinary) from {len(mahs):,} holders; "
                       f"{ratio(len(with_mf), len(prods))}% with a batch-release site from the package leaflet; {(str(sum(1 for s in shorts if s['active'])) + ' open shortage notices') if has_short_src else 'shortages not checked (no national register connected)'}; "
                       f"{(format(len(new12), ',') + ' new authorisations in 12 months') if any(p['date'] for p in prods) else 'no authorisation dates in the register'}"
                       + (f"; EUR {vol_total.get('reimbursed_amount', 0):,.0f} reimbursed for {vol_total.get('reimbursed_packs', 0):,.0f} packs in {vol_meta['period']} (Open Medic)." if has_vol else "; no public volume source."))
            rec = dict(cc=cc, name=COUNTRY_NAME.get(cc, cc), authority=AUTHORITY.get(cc), generated=today.isoformat(), summary=summary, sources=src_list,
                       kpi=dict(products=len(prods), vet=len(prods) - len(human), mahs=len(mahs), apis=len({a for p in prods for a in p["apis"]}),
                                manufacturers=len({(m["name"], m["cc"]) for p in prods for m in mf.get(p["pid"], [])}), with_mf=len(with_mf),
                                shortages_open=sum(1 for s in shorts if s["active"]) if has_short_src else None,
                                new12=len(new12) if any(p["date"] for p in prods) else None,
                                packs=round(vol_total.get("reimbursed_packs", 0)) if has_vol else None, amount=round(vol_total.get("reimbursed_amount", 0)) if has_vol else None,
                                volume_period=vol_meta["period"] if vol_meta else None, volume_source=vol_meta and dict(name=vol_meta["src"], url=vol_meta["url"]),
                                prices=sum(len(v) for v in price.values())),
                       top_subst=dict(metric=metric, rows=[dict(name=k, products=v["products"], packs=round(v["packs"]), amount=round(v["amount"]), slug=v["api_slug"]) for k, v in top_subst]),
                       top_mah=top_mah, top_mah_vol=top_mah_vol,
                       concentration=[dict(api=x["api"], slug=x["slug"], holders=x["kpi"]["mahs"], top_share=x["shares"][0]["share"] if x["shares"] else None,
                                           metric=x["share_metric"]) for x in api_detail.values()],
                       supply=dict(site_groups=dict(site_grp), top_sites=[dict(name=site_label[key][0], cc=key[1], id=site_label[key][1], products=k) for key, k in sites.most_common(15)],
                                   flows=[[a, b, m, n] for (a, b, m), n in flows.most_common(80)],
                                   api_sources=[dict(api=inn.get(a), n=len(dmf_holders[a])) for a in sorted({a for p in prods for a in p["apis"]})]),
                       prices=dict(available=has_price, per_api=[dict(api=x["api"], slug=x["slug"], n=len(x["price_points"]),
                                   min=min((p[1] for p in x["price_points"]), default=None), median=statistics.median([p[1] for p in x["price_points"]]) if x["price_points"] else None,
                                   max=max((p[1] for p in x["price_points"]), default=None), cur=(x["price_points"][0][3] if x["price_points"] else None),
                                   generics=x["kpi"]["generics"], references=x["kpi"]["references"]) for x in api_detail.values()],
                                   source=sorted({x["src"] for v in price.values() for x in v})),
                       shortages=dict(list=shorts[:200], by_month=sorted(Counter((s["date"] or "")[:7] for s in shorts if s["date"]).items())),
                       tenders=tenders[:200], months=sorted(months.items()),
                       recent=[dict(name=p["name"], date=p["date"], mah=p["mah"], src=p["src"]) for p in sorted(new12, key=lambda p: p["date"], reverse=True)[:40]],
                       withdrawals=[s for s in shorts if (s["state"] or "").lower().startswith("arrêt")][:40], gaps=gaps, apis=api_detail)
            dump(rec, out / "mkt" / f"{cc}.json")
            index.append(dict(cc=cc, name=rec["name"], products=len(prods), mahs=len(mahs), with_mf=len(with_mf), apis=rec["kpi"]["apis"], volume=has_vol, prices=has_price, shortages_open=rec["kpi"]["shortages_open"],
                              updated=max((x for x in (vol_meta and vol_meta["period"], today.isoformat()) if x), default=None)))
        dump(index, out / "market_index.json")
        print("market export", len(index), "countries")


if __name__ == "__main__":
    run(Path(sys.argv[1]))
