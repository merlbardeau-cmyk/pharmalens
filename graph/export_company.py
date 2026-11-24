"""Firma 360 export (v2 step 3).

out/search.json          global search index: companies (aliases, group, parent) + APIs
out/company/sNN.json     companies bundled by id % 64; per company: identity, group, roles, aliases, products as MAH, batch-release rows
                         (= CDMO reverse search: who releases for whom, with leaflet quote), DMFs, customers (MAHs)

Every row keeps source_url + status. CDMO relations are derived; when the company has no GLEIF parent the
group check rests on brand groups only -> flag 'group_unverified'.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enrich.company_profile import groups, same_group  # noqa: E402
from graph.export_app import d, dump  # noqa: E402
from models.db import connect  # noqa: E402

SHARDS = 64  # artifact limit: <= 511 files per version -> companies bundled by id % 64
ROLE_LABEL = {"mah": "Zulassungsinhaber", "fdf_manufacturer": "Hersteller Fertigarzneimittel (Chargenfreigabe)",
              "api_manufacturer": "Wirkstoffhersteller", "cdmo": "Lohnhersteller / CDMO"}


def run(out: Path):
    import shutil
    shutil.rmtree(out / "company", ignore_errors=True)
    (out / "company").mkdir(parents=True, exist_ok=True)
    with connect() as c:
        g = groups(c)
        comp = {r[0]: dict(id=r[0], name=r[1], cc=r[2], cc_basis=r[3], lei=r[4], source_url=r[5], status=r[6], aliases=[],
                           roles=[], group=None, parent=None, children=[])
                for r in c.execute("""SELECT company_id, name_raw[1], country, country_basis, lei, source_url, status
                                      FROM company WHERE valid_to IS NULL AND NOT ('brand_group' = ANY(coalesce(roles,'{}')))""")}
        names = {k: v["name"] for k, v in comp.items()}
        names.update(dict(c.execute("SELECT company_id, name_raw[1] FROM company WHERE valid_to IS NULL").fetchall()))
        for cid, al, kind, n, seen, st in c.execute("""SELECT company_id, alias, kind, n_observed, seen_in, status FROM company_alias
                                                       WHERE valid_to IS NULL ORDER BY n_observed DESC NULLS LAST""").fetchall():
            if cid in comp:
                comp[cid]["aliases"].append(dict(a=al, k=kind, n=n, src=seen, st=st))
        lei_parent = set()
        for p, ch, rt, url, st in c.execute("""SELECT parent_id, child_id, relation_type, source_url, status FROM company_relation
                                               WHERE valid_to IS NULL""").fetchall():
            if ch not in comp:
                continue
            if rt == "brand_group_member":
                comp[ch]["group"] = dict(name=names.get(p), status=st, basis="Markengruppe (Namensstamm)")
            elif rt in ("subsidiary", "ultimate_parent"):
                lei_parent.add(ch)
                if rt == "ultimate_parent" or not comp[ch]["parent"]:
                    comp[ch]["parent"] = dict(id=p, name=names.get(p), type=rt, source_url=url, status=st)
                if p in comp:
                    comp[p]["children"].append(dict(id=ch, name=names.get(ch), type=rt, source_url=url, status=st))
        for cid, role, npd, napi, nmk, rat, st in c.execute("""SELECT company_id, role, n_products, n_apis, n_markets, rationale, status
                                                              FROM company_role WHERE valid_to IS NULL""").fetchall():
            if cid in comp:
                comp[cid]["roles"].append(dict(role=role, label=ROLE_LABEL.get(role, role), products=npd, apis=napi, markets=nmk,
                                               rationale=rat, status=st,
                                               group_unverified=(role == "cdmo" and cid not in lei_parent)))
        inn = dict(c.execute("SELECT api_id, inn FROM api WHERE valid_to IS NULL AND parent_api_id IS NULL").fetchall())
        papi = defaultdict(set)
        for pid, aid in c.execute("SELECT product_id, api_id FROM product_api").fetchall():
            papi[pid].add(inn.get(aid))
        prod = {}
        for r in c.execute("""SELECT product_id, name, country, mah_company_id, mah_raw, authorisation_no, auth_date, form,
                                     procedure, substances_raw, source_url, status, leaflet_url FROM product WHERE valid_to IS NULL"""):
            prod[r[0]] = dict(pid=r[0], name=r[1], cc=r[2], mah_id=r[3], mah=r[4], no=r[5], date=d(r[6]), form=r[7], proc=r[8],
                              subst=", ".join(sorted(x for x in papi[r[0]] if x)) or (r[9] or "")[:120], src=r[10], st=r[11],
                              leaf=r[12])
        mah_of = defaultdict(list)
        for p in prod.values():
            if p["mah_id"] in comp:
                mah_of[p["mah_id"]].append(p)
        rel = defaultdict(list)
        for pm in c.execute("""SELECT company_id, product_id, role, manufacturer_raw, site_country, evidence_quote, leaflet_url,
                                      source_url, status FROM product_manufacturer WHERE valid_to IS NULL AND company_id IS NOT NULL""").fetchall():
            cid, pid, role, raw, scc, q, leaf, src, st = pm
            p = prod.get(pid)
            if cid not in comp or not p:
                continue
            foreign = st == "official" and p["mah_id"] is not None and not same_group(g, cid, p["mah_id"])
            rel[cid].append(dict(pid=pid, product=p["name"], cc=p["cc"], subst=p["subst"], mah=p["mah"], mah_id=p["mah_id"],
                                 foreign=foreign, role=role, site_cc=scc, quote=q, leaflet=leaf, src=src, st=st, date=p["date"]))
        dmf = defaultdict(list)
        for cid, aid, no, cs, issued, src, st in c.execute("""SELECT holder_company_id, api_id, number, cert_status, issue_date, source_url,
                                                              status FROM api_certificate WHERE valid_to IS NULL""").fetchall():
            if cid in comp:
                dmf[cid].append(dict(api=inn.get(aid), no=no, cs=cs, date=d(issued), src=src, st=st))

        search, n, shards = [], 0, defaultdict(dict)
        for cid, x in comp.items():
            if not (x["roles"] or rel[cid] or dmf[cid]):
                continue
            cust = defaultdict(lambda: dict(products=0, cc=set()))
            for r in rel[cid]:
                if r["foreign"]:
                    k = r["mah"] or "?"
                    cust[k]["products"] += 1
                    cust[k]["cc"].add(r["cc"])
            customers = sorted([dict(mah=k, products=v["products"], cc=sorted(v["cc"])) for k, v in cust.items()],
                               key=lambda z: -z["products"])
            x.update(as_mah=sorted(({k: v for k, v in p.items() if k != "mah_id"} for p in mah_of[cid]), key=lambda z: (z["cc"], z["name"] or "")),
                     manufacturing=rel[cid], dmf=dmf[cid], customers=customers,
                     kpi=dict(mah_products=len(mah_of[cid]), released=len({r["pid"] for r in rel[cid]}),
                              foreign_released=len({r["pid"] for r in rel[cid] if r["foreign"]}), customers=len(customers),
                              markets=len({r["cc"] for r in rel[cid]} | {p["cc"] for p in mah_of[cid]}), dmf=len(dmf[cid])))
            shards[cid % SHARDS][cid] = x
            n += 1
            search.append(dict(t="c", id=cid, n=x["name"], cc=x["cc"], al=list({a["a"] for a in x["aliases"]})[:12],
                               g=(x["group"] or {}).get("name"), p=(x["parent"] or {}).get("name"),
                               r=sorted({r["role"] for r in x["roles"]}), k=x["kpi"], lei=bool(x["lei"]),
                               w=x["kpi"]["released"] + x["kpi"]["mah_products"]))
        for k, v in shards.items():
            dump(v, out / "company" / f"s{k:02d}.json")
        search.sort(key=lambda z: -z["w"])
        dump(search, out / "search.json")
        print("company export", n, "companies")


if __name__ == "__main__":
    run(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "app" / "out")
