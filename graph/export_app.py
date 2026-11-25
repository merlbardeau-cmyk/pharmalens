"""Export the PharmaLens DB to the static JSON files the Explorer app reads.

out/apis.json            index + totals
out/api/<slug>.json      detail per API (loaded on demand)
out/companies.json       manufacturers across all APIs (batch-release sites + API makers)
out/markets.json         per country: products, MAHs, leaflet coverage
out/sources.json         source register with traffic light
out/gaps.json            open gaps grouped
Usage: python graph/export_app.py <out_dir>
"""
from __future__ import annotations

import datetime
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graph.i18n_en import en  # noqa: E402
from models.db import connect  # noqa: E402
from models.pilot import PILOT  # noqa: E402

COUNTRY_NAME = {"AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CH": "Switzerland", "CY": "Cyprus", "CZ": "Czechia",
                "DE": "Germany", "DK": "Denmark", "EE": "Estonia", "ES": "Spain", "EU": "EU central", "FI": "Finland",
                "FR": "France", "GB": "United Kingdom", "GR": "Greece", "HR": "Croatia", "HU": "Hungary",
                "IE": "Ireland", "IS": "Iceland", "IT": "Italy", "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg",
                "LV": "Latvia", "MT": "Malta", "NL": "Netherlands", "NO": "Norway", "PL": "Poland", "PT": "Portugal",
                "RO": "Romania", "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia", "US": "USA", "XI": "Northern Ireland",
                "IN": "India", "CN": "China", "IL": "Israel", "TR": "Türkiye", "JP": "Japan", "KR": "South Korea", "MK": "North Macedonia",
                "RS": "Serbia", "BA": "Bosnia and Herzegovina"}
LEAFLET_SOURCES = ("ES AEMPS CIMA REST", "FR BDPM", "NL CBG Geneesmiddeleninformatiebank", "AT BASG Arzneispezialitätenregister", "DK DKMA")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def d(x):
    return x.isoformat() if isinstance(x, (datetime.date, datetime.datetime)) else x


def dump(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str))


def run(out: Path):
    group = {i: g for i, g, _ in PILOT}
    summ_file = Path(__file__).resolve().parents[1] / "reports" / "pilot_export" / "zusammenfassung.json"
    summ = {x["inn"]: x["summary"] for x in json.loads(summ_file.read_text())} if summ_file.exists() else {}
    with connect() as c:
        apis = c.execute("""SELECT a.api_id, a.inn, a.unii, a.cas, a.atc, a.is_veterinary, a.source_url,
              (SELECT array_agg(s.salt_form ORDER BY s.salt_form) FROM api s WHERE s.parent_api_id=a.api_id AND s.valid_to IS NULL)
              FROM api a WHERE a.parent_api_id IS NULL AND a.valid_to IS NULL ORDER BY a.inn""").fetchall()
        index, inn_of = [], {}
        cname = dict(c.execute("SELECT company_id, name_raw[1] FROM company WHERE valid_to IS NULL").fetchall())
        cc_of = dict(c.execute("SELECT company_id, country FROM company WHERE valid_to IS NULL").fetchall())
        for aid, inn, unii, cas, atc, vet, src, salts in apis:
            inn_of[aid] = inn
            P = c.execute("""SELECT p.product_id,p.country,p.name,p.mah_raw,p.authorisation_no,p.strength,p.form,p.procedure,
                                    p.product_status,p.is_veterinary,p.status,p.source_name,p.source_url,p.leaflet_url,p.mah_company_id
                             FROM product p JOIN product_api pa USING(product_id) WHERE pa.api_id=%s AND p.valid_to IS NULL
                             ORDER BY p.country,p.name""", (aid,)).fetchall()
            M = c.execute("""SELECT pm.product_id,p.country,p.name,pm.role,pm.manufacturer_raw,pm.site_address_raw,pm.site_country,
                                    pm.evidence_quote,pm.leaflet_url,pm.status,pm.source_name,pm.company_id
                             FROM product_manufacturer pm JOIN product p ON p.product_id=pm.product_id AND p.valid_to IS NULL
                             JOIN product_api pa ON pa.product_id=p.product_id
                             WHERE pa.api_id=%s AND pm.valid_to IS NULL ORDER BY pm.manufacturer_raw""", (aid,)).fetchall()
            C = c.execute("""SELECT c.cert_type,c.number,c.cert_status,c.issue_date,c.holder_raw,co.country,c.substance_raw,c.status,c.source_url
                             FROM api_certificate c LEFT JOIN company co ON co.company_id=c.holder_company_id AND co.valid_to IS NULL
                             WHERE c.api_id=%s AND c.valid_to IS NULL ORDER BY c.cert_status,c.holder_raw""", (aid,)).fetchall()
            T = c.execute("""SELECT number,jurisdiction,patent_type,expiry,patent_status,status,source_url FROM patent
                             WHERE api_id=%s AND valid_to IS NULL ORDER BY expiry DESC""", (aid,)).fetchall()
            S = c.execute("""SELECT event_date,detail,status,source_url FROM event WHERE event_type='shortage' AND entity_ref=%s
                             ORDER BY event_date DESC""", (aid,)).fetchall()
            D = c.execute("""SELECT notice_id,award_date,buyer,winner_raw,value,currency,source_url FROM tender WHERE api_id=%s
                             ORDER BY award_date DESC LIMIT 100""", (aid,)).fetchall()
            G = c.execute("""SELECT area,reason,where_obtainable FROM gap WHERE resolved_at IS NULL
                             AND (entity_ref IN (SELECT product_id::text FROM product_api WHERE api_id=%s) OR entity_ref=%s)
                             GROUP BY 1,2,3""", (aid, inn)).fetchall()
            prods = [dict(id=r[0], cc=r[1], name=r[2], mah=r[3], no=r[4], str=r[5], form=r[6], proc=r[7], st=r[8], vet=r[9],
                          status=r[10], src=r[11], url=r[12], pil=r[13]) for r in P]
            mfr = [dict(pid=r[0], cc=r[1], product=r[2], role=r[3], company=r[4], addr=r[5], site_cc=r[6], quote=r[7], url=r[8],
                        status=r[9], src=r[10]) for r in M]
            certs = [dict(type=r[0], no=r[1], cs=r[2], date=d(r[3]), holder=r[4], holder_cc=r[5], subject=r[6], status=r[7], url=r[8]) for r in C]
            pats = [dict(no=r[0], jur=r[1], type=r[2], exp=d(r[3]), ps=r[4], status=r[5], url=r[6]) for r in T]
            short = [dict(date=d(r[0]), **{k: r[1].get(k) for k in ("country", "product", "state", "active", "type", "expected_resolution")},
                          status=r[2], url=r[3]) for r in S]
            tend = [dict(id=r[0], date=d(r[1]), buyer=r[2], winner=r[3], value=float(r[4]) if r[4] is not None else None, cur=r[5], url=r[6]) for r in D]
            gaps = [dict(area=r[0], reason=en(r[1]), where=r[2]) for r in G]
            sites = {(m["company"], m["site_cc"]) for m in mfr if m["role"] == "batch_release"}
            countries = sorted({p["cc"] for p in prods if p["cc"] != "EU"})
            # customers (derived) and supply-chain flows site -> MAH -> market (official leaflet links only)
            cust = [dict(id=r[0], name=cname.get(r[0]), score=float(r[1]), reasons=r[2], products=r[3], markets=r[4], cc=cc_of.get(r[0]))
                    for r in c.execute("""SELECT company_id, score, reasons, n_products, n_countries FROM potential_customer
                                          WHERE valid_to IS NULL AND api_id=%s ORDER BY score DESC""", (aid,)).fetchall()]
            sites_of = defaultdict(set)
            for r in M:
                if r[3] == "batch_release" and r[9] == "official":
                    sites_of[r[0]].add(cname.get(r[11]) or r[4])
            flows = defaultdict(float)
            for r in P:
                mah = cname.get(r[14]) or r[3] or "Holder unknown"
                ss = sites_of.get(r[0]) or {"Site not in leaflet"}
                for site in ss:
                    flows[(site, mah, r[1])] += 1 / len(ss)
            dump(dict(inn=inn, unii=unii, cas=cas, atc=atc, vet=vet, src=src, salts=salts or [], summary=en(summ.get(inn)), group=group.get(inn),
                      products=prods, manufacturers=mfr, certificates=certs, patents=pats, shortages=short, tenders=tend, gaps=gaps,
                      customers=cust, flows=[[a, b, cc, round(v, 2)] for (a, b, cc), v in flows.items()]),
                 out / "api" / f"{slug(inn)}.json")
            index.append(dict(slug=slug(inn), inn=inn, group=group.get(inn), unii=unii, cas=cas, atc=(atc or [None])[0], vet=vet,
                              salts=len(salts or []), products=len(prods), countries=len(countries),
                              central=any(p["cc"] == "EU" for p in prods), mahs=len({p["mah"] for p in prods if p["mah"]}),
                              dmf_active=len({x["holder"] for x in certs if x["type"] == "US_DMF" and x["cs"] == "active"}),
                              sites=len(sites), leaflets=len({m["pid"] for m in mfr if m["role"] == "batch_release"}),
                              us_patent=max([p["exp"] for p in pats if p["type"] == "substance"] or [None]),
                              shortages=sum(1 for s in short if s.get("active") is not False and s.get("state") != "Resolved"),
                              tenders=len(tend), gaps=len(gaps), summary=en(summ.get(inn))))

        # companies (batch-release sites + API makers), keyed by resolved company
        comp = defaultdict(lambda: dict(name=None, cc=set(), roles=set(), apis=set(), products=set(), markets=set(), dmf=0, group=None, lei=None))
        for cid, name, cc, lei, aid, pid, mcc, role in c.execute("""
                SELECT co.company_id, co.name_raw[1], pm.site_country, co.lei, pa.api_id, pm.product_id, p.country, pm.role
                FROM product_manufacturer pm JOIN company co ON co.company_id=pm.company_id AND co.valid_to IS NULL
                JOIN product p ON p.product_id=pm.product_id AND p.valid_to IS NULL JOIN product_api pa ON pa.product_id=p.product_id
                WHERE pm.valid_to IS NULL""").fetchall():
            x = comp[cid]
            x["name"], x["lei"] = x["name"] or name, lei
            x["cc"].add(cc)
            x["roles"].add("API manufacturer (Annex IIA)" if role == "api_manufacturer" else "Batch release")
            x["apis"].add(inn_of.get(aid))
            x["products"].add(pid)
            x["markets"].add(mcc)
        for cid, name, cc, lei, aid, cs in c.execute("""
                SELECT co.company_id, co.name_raw[1], co.country, co.lei, a.api_id, a.cert_status FROM api_certificate a
                JOIN company co ON co.company_id=a.holder_company_id AND co.valid_to IS NULL WHERE a.valid_to IS NULL""").fetchall():
            x = comp[cid]
            x["name"], x["lei"] = x["name"] or name, x["lei"] or lei
            if cc:
                x["cc"].add(cc)
            x["roles"].add("API manufacturer (US DMF)")
            x["apis"].add(inn_of.get(aid))
            x["dmf"] += 1
        for child, gname in c.execute("""SELECT r.child_id, g.name_raw[1] FROM company_relation r JOIN company g ON g.company_id=r.parent_id
                                         AND g.valid_to IS NULL WHERE r.relation_type='brand_group_member' AND r.valid_to IS NULL""").fetchall():
            if child in comp:
                comp[child]["group"] = gname
        parents = dict(c.execute("""SELECT r.child_id, p.name_raw[1] FROM company_relation r JOIN company p ON p.company_id=r.parent_id
                                    AND p.valid_to IS NULL WHERE r.relation_type='ultimate_parent' AND r.valid_to IS NULL""").fetchall())
        companies = sorted([dict(id=k, name=v["name"], cc=sorted(x for x in v["cc"] if x), roles=sorted(v["roles"]),
                                 apis=sorted(x for x in v["apis"] if x), products=len(v["products"]),
                                 markets=sorted(x for x in v["markets"] if x), dmf=v["dmf"], group=v["group"], lei=v["lei"],
                                 parent=parents.get(k)) for k, v in comp.items() if v["name"]],
                           key=lambda x: (-x["products"], -x["dmf"], x["name"]))
        dump(companies, out / "companies.json")

        # markets
        mk = c.execute("""SELECT p.country, count(DISTINCT p.product_id), count(DISTINCT p.mah_raw),
                   count(DISTINCT p.product_id) FILTER (WHERE EXISTS (SELECT 1 FROM product_manufacturer m WHERE m.product_id=p.product_id
                         AND m.valid_to IS NULL AND m.role='batch_release')),
                   count(DISTINCT p.product_id) FILTER (WHERE p.source_name = ANY(%s)),
                   array_agg(DISTINCT p.source_name), count(DISTINCT pa.api_id),
                   count(DISTINCT p.product_id) FILTER (WHERE p.is_veterinary)
                   FROM product p JOIN product_api pa USING (product_id) WHERE p.valid_to IS NULL GROUP BY 1 ORDER BY 2 DESC""",
                       (list(LEAFLET_SOURCES),)).fetchall()
        markets = [dict(cc=r[0], name=COUNTRY_NAME.get(r[0], r[0]), products=r[1], mahs=r[2], with_mfr=r[3], leaflet_products=r[4],
                        sources=sorted(r[5]), apis=r[6], vet=r[7]) for r in mk]
        dump(markets, out / "markets.json")

        # sources
        src_rows = c.execute("""SELECT name, category, jurisdiction, traffic_light, access_method, traffic_reason, licence_note,
                                       update_frequency, probe_url FROM source ORDER BY
                                       array_position(ARRAY['green','yellow','red'], traffic_light), category, name""").fetchall()
        dump([dict(name=r[0], cat=r[1], jur=r[2], light=r[3], access=r[4], reason=en(r[5]), licence=en(r[6]), freq=en(r[7]), url=r[8]) for r in src_rows],
             out / "sources.json")

        # gaps grouped
        g = c.execute("""SELECT area, reason, count(*), min(where_obtainable) FROM gap WHERE resolved_at IS NULL
                         GROUP BY 1,2 ORDER BY 3 DESC""").fetchall()
        dump([dict(area=r[0], reason=en(r[1]), n=r[2], where=r[3]) for r in g], out / "gaps.json")

        totals = dict(
            products=c.execute("SELECT count(*) FROM product WHERE valid_to IS NULL").fetchone()[0],
            sites=c.execute("SELECT count(*) FROM product_manufacturer WHERE valid_to IS NULL AND role='batch_release'").fetchone()[0],
            dmf=c.execute("SELECT count(*) FROM api_certificate WHERE valid_to IS NULL").fetchone()[0],
            sources=c.execute("SELECT count(*) FROM source WHERE traffic_light<>'red'").fetchone()[0],
            sources_all=c.execute("SELECT count(*) FROM source").fetchone()[0],
            gaps=c.execute("SELECT count(*) FROM gap WHERE resolved_at IS NULL").fetchone()[0],
            companies=len(companies), countries=len([m for m in markets if m["cc"] != "EU"]),
            confirmed=c.execute("SELECT count(*) FROM supply_link WHERE confidence='confirmed'").fetchone()[0],
            derived=c.execute("SELECT count(*) FROM supply_link WHERE confidence='derived'").fetchone()[0])
        dump(dict(generated=datetime.date.today().isoformat(), totals=totals, apis=index), out / "apis.json")
        print("export", totals, "companies", len(companies), "markets", len(markets))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
