"""Manufacturer 360 export (API manufacturers).

out/mfr/sNN.json   manufacturers bundled by id % 16

Only what the data holds is shown as a value. Certificate types and compliance sources that are not connected are
exported as status 'not_checked' with the reason - never as 0. Derived items (possible parent from name, potential
customers, supply links without document) carry status 'derived' and a rationale.
"""
from __future__ import annotations

import re
import shutil
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enrich.company_profile import groups, same_group  # noqa: E402
from graph.export_app import COUNTRY_NAME, d, dump  # noqa: E402
from graph.i18n_en import en  # noqa: E402
from models.db import connect  # noqa: E402

SHARDS = 16
EEA = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
       "PL", "PT", "RO", "SK", "SI", "ES", "SE", "IS", "LI", "NO", "EU", "XI"}
NOT_CONNECTED = {  # certificate / compliance sources not yet connected, with the reason (see Sources page)
    "CEP": "EDQM CEP database: licence request pending",
    "JDMF": "PMDA MF register not connected",
    "KDMF": "MFDS DMF register not connected",
    "WC": "Written Confirmations: CDSCO blocks access",
    "WHO-PQ": "No WHO-PQ API listing for the pilot APIs found / not matched",
    "EU-GMP": "EudraGMDP returns no results for automated queries",
}
COMPLIANCE = {
    "FDA inspections": "FDA inspection classification database not connected",
    "Warning Letters": "FDA Warning Letter index not connected",
    "Import Alerts": "FDA Import Alert lists not connected",
    "EU non-compliance": "EudraGMDP non-compliance reports: no results for automated queries",
}
LEGAL = {"LTD": "Ltd.", "LIMITED": "Limited", "CO": "Co.", "CO.": "Co.", "INC": "Inc.", "INC.": "Inc.", "LLC": "LLC", "PLC": "plc",
         "GMBH": "GmbH", "AG": "AG", "SA": "S.A.", "S.A.": "S.A.", "SL": "S.L.", "S.L.": "S.L.", "SPA": "S.p.A.", "S.P.A.": "S.p.A.",
         "SRL": "S.r.l.", "S.R.L.": "S.r.l.", "BV": "B.V.", "B.V.": "B.V.", "AB": "AB", "AS": "AS", "A/S": "A/S", "KG": "KG",
         "PVT": "Pvt.", "PVT.": "Pvt.", "PTE": "Pte.", "D.O.O.": "d.o.o.", "KFT": "Kft.", "SAS": "SAS", "S.A.S.": "S.A.S.",
         "OY": "Oy", "NV": "N.V.", "N.V.": "N.V.", "CORP": "Corp.", "CORPORATION": "Corporation", "SE": "SE"}
LOWER_SHORT = {"OF", "DE", "LA", "DI", "DO", "DA", "EL", "LE", "DU", "Y", "E", "DR", "ST", "MR"}
KEEP_UPPER = {"API", "APIS", "USA", "UK", "USP", "EP", "R&D", "LTDA", "II", "III", "IV", "MSN", "TAPI", "SMS", "DRL", "GSK", "MSD",
              "CSPC", "BASF", "DSM", "AMRI", "HEC", "NCPC", "SPL", "IOL", "ZCL"}


def normalise(name: str) -> str:
    out = []
    for w in (name or "").split():
        u = w.upper().strip(",")
        tail = "," if w.endswith(",") else ""
        if u in LEGAL:
            out.append(LEGAL[u] + tail)
        elif u in KEEP_UPPER or re.search(r"\d", u) or ("." in u.strip(".") and w.isupper()) or (len(u) <= 2 and u.isalpha() and u not in LOWER_SHORT):
            out.append(w)
        elif w.isupper() or w.islower():
            out.append("-".join(p[:1].upper() + p[1:].lower() for p in w.split("-")))
        else:
            out.append(w)
    s = " ".join(out)
    return re.sub(r"\(([a-z])", lambda m: "(" + m.group(1).upper(), s)


def possible_parent(name: str):
    m = re.match(r"^(.*?\b(?:Group|Holdings?))\b(.+)$", normalise(name), re.I)
    if m:
        rest = [w for w in re.split(r"[\s,]+", m.group(2)) if w and w.upper().strip(",") not in LEGAL and w.rstrip(".") not in {x.rstrip(".") for x in LEGAL.values()}]
        if len(" ".join(rest)) > 3:  # a real company name follows the group name -> group is a possible parent
            return m.group(1).strip(" ,")
    return None


def run(out: Path, today: date | None = None):
    today = today or date.today()
    shutil.rmtree(out / "mfr", ignore_errors=True)
    (out / "mfr").mkdir(parents=True, exist_ok=True)
    with connect() as c:
        q = lambda sql, *a: c.execute(sql, a).fetchall()  # noqa: E731
        g = groups(c)
        inn = dict(q("SELECT api_id, inn FROM api WHERE valid_to IS NULL AND parent_api_id IS NULL"))
        comp = {r[0]: r for r in q("""SELECT company_id, name_raw, country, country_basis, lei, source_url, status, name_normalized
                                     FROM company WHERE valid_to IS NULL""")}
        key_to_id = {r[7]: r[0] for r in comp.values()}
        roles = defaultdict(dict)
        for cid, role, npd, rat, st in q("SELECT company_id, role, n_products, rationale, status FROM company_role WHERE valid_to IS NULL"):
            roles[cid][role] = dict(n=npd, rationale=rat, status=st)
        certs = defaultdict(list)
        holders = defaultdict(set)
        for cid, aid, no, cs, dt, subj, raw, url, st in q("""SELECT holder_company_id, api_id, number, cert_status, issue_date,
                substance_raw, holder_raw, source_url, status FROM api_certificate WHERE valid_to IS NULL AND holder_company_id IS NOT NULL"""):
            certs[cid].append(dict(type="US-DMF", api=inn.get(aid), api_id=aid, no=no, cs=cs, date=d(dt), subject=subj, raw=raw, url=url, st=st))
            if cs == "active":
                holders[aid].add(cid)
        annex = defaultdict(list)
        for cid, pid, addr, scc, qt, url, st, mah, pname, pcc in q("""
                SELECT pm.company_id, pm.product_id, pm.site_address_raw, pm.site_country, pm.evidence_quote, pm.leaflet_url, pm.status,
                       p.mah_company_id, p.name, p.country
                FROM product_manufacturer pm JOIN product p ON p.product_id=pm.product_id AND p.valid_to IS NULL
                WHERE pm.valid_to IS NULL AND pm.role='api_manufacturer' AND pm.company_id IS NOT NULL"""):
            annex[cid].append(dict(pid=pid, addr=addr, cc=scc, quote=qt, url=url, st=st, mah=mah, product=pname, pcc=pcc))
        papi = defaultdict(set)
        for pid, aid in q("SELECT product_id, api_id FROM product_api"):
            papi[pid].add(aid)
        eu_products = defaultdict(int)
        for aid, cc, n in q("""SELECT pa.api_id, p.country, count(DISTINCT p.product_id) FROM product p JOIN product_api pa USING (product_id)
                               WHERE p.valid_to IS NULL GROUP BY 1,2"""):
            if cc in EEA:
                eu_products[aid] += n
        pat = {}
        for aid, exp, typ in q("SELECT api_id, max(expiry), string_agg(DISTINCT patent_type, ',') FROM patent WHERE valid_to IS NULL AND patent_type IN ('substance','formulation','use') GROUP BY 1"):
            pat[aid] = dict(us_expiry=d(exp), types=typ)
        shortage_open = {aid for (aid,) in q("SELECT DISTINCT api_id FROM signal WHERE valid_to IS NULL AND signal_type='shortage'")}
        pcs = defaultdict(list)
        for aid, cid, score, reasons, npd, ncc in q("""SELECT api_id, company_id, score, reasons, n_products, n_countries
                                                      FROM potential_customer WHERE valid_to IS NULL"""):
            pcs[aid].append((cid, float(score), reasons, npd, ncc))
        aliases = defaultdict(list)
        for cid, al, kind, n, seen, st in q("SELECT company_id, alias, kind, n_observed, seen_in, status FROM company_alias WHERE valid_to IS NULL"):
            aliases[cid].append(dict(a=al, k=kind, n=n, src=seen, st=st))
        sigs = defaultdict(list)
        for cid, t, dt, ti, aid, url, st in q("""SELECT company_id, signal_type, signal_date, title, api_id, source_url, status FROM signal
                                                WHERE valid_to IS NULL AND company_id IS NOT NULL AND signal_type='new_dmf'"""):
            sigs[cid].append(dict(type=t, date=d(dt), title=ti, api=inn.get(aid), url=url, st=st))
        parents = {ch: (p, rt, url, st) for p, ch, rt, url, st in q("""SELECT parent_id, child_id, relation_type, source_url, status
                   FROM company_relation WHERE valid_to IS NULL AND relation_type IN ('ultimate_parent','subsidiary')""")}
        brand = {ch: p for p, ch in q("SELECT parent_id, child_id FROM company_relation WHERE valid_to IS NULL AND relation_type='brand_group_member'")}
        soon = d(today + timedelta(days=730))

        shards, index = defaultdict(dict), []
        for cid, r in comp.items():
            if "api_manufacturer" not in roles[cid] and not certs[cid] and not annex[cid]:
                continue
            raw_name = (r[1] or [""])[0]
            name = normalise(raw_name)
            # country: register value, else Annex IIA site country (all sites in one country), else gap
            if r[2]:
                country = dict(cc=r[2], basis=en(r[3]) or "company register", status=r[6])
            elif annex[cid] and len({a["cc"] for a in annex[cid] if a["cc"]}) == 1:
                country = dict(cc=annex[cid][0]["cc"], basis="site country in EMA Annex IIA", status="official")
            else:
                country = dict(cc=None, basis=None, status="gap",
                               reason="Country not stated in source (US DMF list has no address); CEP, EudraGMDP, FDA FEI and Written Confirmations not connected")
            # group
            if cid in parents:
                p, rt, url, st = parents[cid]
                group = dict(name=normalise((comp.get(p, (0, [""]))[1] or [""])[0]), id=p, status=st, basis=f"GLEIF {rt.replace('_', ' ')}", url=url)
            else:
                pp = possible_parent(raw_name)
                if pp:
                    pid = key_to_id.get(re.sub(r"[^a-z0-9]+", " ", pp.lower()).strip())
                    group = dict(name=pp, id=pid, status="derived", basis="Possible parent: the company name starts with this group name. "
                                 "Not confirmed by GLEIF or a company register.")
                elif cid in brand:
                    group = dict(name=normalise((comp.get(brand[cid], (0, [""]))[1] or [""])[0]), id=None, status="derived", basis="Brand group (name stem)")
                else:
                    group = dict(name=None, status="gap", reason="No group found in GLEIF; name gives no group hint")
            # portfolio: one row per API
            port = {}
            for ce in certs[cid]:
                row = port.setdefault(ce["api_id"], dict(api=ce["api"], api_id=ce["api_id"], dmf=[], annex=[]))
                row["dmf"].append({k: ce[k] for k in ("no", "cs", "date", "subject", "url", "st")})
            for a in annex[cid]:
                for aid in papi[a["pid"]]:
                    row = port.setdefault(aid, dict(api=inn.get(aid), api_id=aid, dmf=[], annex=[]))
                    if len(row["annex"]) < 5:
                        row["annex"].append(dict(product=a["product"], cc=a["pcc"], url=a["url"], st=a["st"]))
            for aid, row in port.items():
                row.update(eu_products=eu_products.get(aid, 0), patent=pat.get(aid),
                           competitors=len(holders[aid] - {cid}), shortage=aid in shortage_open,
                           not_checked={k: v for k, v in NOT_CONNECTED.items()})
            # sites: Annex IIA addresses only (DMF list carries none)
            sites = {}
            for a in annex[cid]:
                k = (a["addr"] or "").lower()[:40]
                s = sites.setdefault(k, dict(addr=a["addr"], cc=a["cc"], quote=a["quote"], url=a["url"], st=a["st"], products=0,
                                             fei=None, eudragmdp=None))
                s["products"] += 1
            # potential customers across the portfolio (derived)
            cust = {}
            own_apis = {aid for aid, row in port.items() if any(x["cs"] == "active" for x in row["dmf"]) or row["annex"]}
            evid = defaultdict(list)
            for a in annex[cid]:
                if a["mah"]:
                    evid[a["mah"]].append(dict(product=a["product"], cc=a["pcc"], url=a["url"]))
            for aid in own_apis:
                bonus, why = 0, []
                if aid in shortage_open:
                    bonus += 15; why.append(f"open shortage for {inn.get(aid)}")
                pp = pat.get(aid)
                if pp and pp["us_expiry"] and d(today) <= pp["us_expiry"] <= soon:
                    bonus += 10; why.append(f"US patent for {inn.get(aid)} expires {pp['us_expiry']}")
                if 0 < len(holders[aid]) <= 5:
                    bonus += 10; why.append(f"only {len(holders[aid])} active US DMF holders for {inn.get(aid)}")
                for mah, score, reasons, npd, ncc in pcs[aid]:
                    if same_group(g, mah, cid):
                        continue
                    x = cust.setdefault(mah, dict(id=mah, name=(comp.get(mah, (0, [""]))[1] or [""])[0], score=0, apis=[],
                                                  products=0, markets=0, reasons=[], evidence=evid.get(mah, []), status="derived"))
                    x["score"] += score + bonus
                    x["apis"].append(inn.get(aid))
                    x["products"] += npd or 0
                    x["markets"] = max(x["markets"], ncc or 0)
                    x["reasons"] += [f"{inn.get(aid)}: {npd} products in {ncc} markets"] + why
            for mah, ev in evid.items():
                if mah in cust:
                    cust[mah]["status"] = "official"
                    cust[mah]["reasons"].insert(0, f"Named as API manufacturer for {len(ev)} of its products in EMA Annex IIA")
            customers = sorted(cust.values(), key=lambda x: -x["score"])[:250]
            for x in customers:
                x["reasons"] = list(dict.fromkeys(x["reasons"]))[:6]
                x["score"] = round(x["score"])
            n_active = sum(1 for ce in certs[cid] if ce["cs"] == "active")
            gaps = [dict(area="Certificates", reason=f"{k}: {v}") for k, v in NOT_CONNECTED.items()]
            gaps += [dict(area="Compliance", reason=f"{k}: {v}") for k, v in COMPLIANCE.items()]
            if country["status"] == "gap":
                gaps.insert(0, dict(area="Country", reason=country["reason"]))
            if not sites:
                gaps.insert(0, dict(area="Sites", reason="No site address in the US DMF list; FDA establishment (FEI) and EudraGMDP not connected"))
            gaps.append(dict(area="EU DMF hints", reason="No data basis yet: needs CEP or ASMF data"))
            apis_txt = ", ".join(sorted({row["api"] for row in port.values() if row["api"]}))
            summary = (f"{name}: {n_active} active US DMF{'s' if n_active != 1 else ''} (type II) for {len(own_apis)} pilot API"
                       f"{'s' if len(own_apis) != 1 else ''} ({apis_txt}); CEP, JDMF, KDMF and Written Confirmations not checked; "
                       f"{len(sites) if sites else 'no'} known site{'s' if len(sites) != 1 else ''}; GMP status not checked.")
            rset = set(roles[cid])
            other = rset - {"api_manufacturer"}
            fdf_weight = sum((roles[cid].get(k) or {}).get("n") or 0 for k in ("mah", "fdf_manufacturer", "cdmo"))
            primary = "manufacturer" if not other or len(certs[cid]) >= fdf_weight else "company"
            rec = dict(id=cid, name=name, original=raw_name, country=country, group=group, lei=r[4], roles=sorted(rset), primary=primary,
                       summary=summary, portfolio=sorted(port.values(), key=lambda x: x["api"] or ""), sites=list(sites.values()),
                       compliance=[dict(kind=k, status="not_checked", reason=v) for k, v in COMPLIANCE.items()],
                       eu_dmf_hints=[], customers=customers, signals=sorted(sigs[cid], key=lambda x: x["date"] or "", reverse=True),
                       aliases=[dict(a=raw_name, k="source_name", n=None, src=["FDA DMF list" if certs[cid] else "EMA Annex IIA"], st="official")]
                       + aliases[cid], gaps=gaps,
                       kpi=dict(apis=len(own_apis), dmf_active=n_active, dmf_total=len(certs[cid]), sites=len(sites),
                                customers=len(customers), customers_evidenced=sum(1 for x in customers if x["status"] == "official")))
            shards[cid % SHARDS][cid] = rec
            index.append(dict(id=cid, n=name, cc=country["cc"], apis=sorted({row["api"] for row in port.values() if row["api"]}),
                              dmf=n_active, sites=len(sites), g=group.get("name"), gs=group.get("status"), cust=len(customers),
                              primary=primary, roles=sorted(rset)))
        for k, v in shards.items():
            dump(v, out / "mfr" / f"s{k:02d}.json")
        index.sort(key=lambda x: (-x["dmf"], x["n"]))
        dump(index, out / "manufacturers.json")
        print("manufacturer export", len(index), "manufacturers,", sum(1 for x in index if x["primary"] == "manufacturer"), "primary")


if __name__ == "__main__":
    run(Path(sys.argv[1]))
