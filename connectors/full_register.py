"""Full-register ingest for the CDMO reverse search (v2 step 3, decision 3: ES + FR first).

Products outside the 20-API pilot are written with their register substance text (product.substances_raw) and,
where the pilot matcher hits, the usual product_api link. Then the package leaflet of every product without a
manufacturer row is parsed (same parser + precision rules as the pilot), so any company can be searched as
batch-release site across the whole register.

    python connectors/full_register.py fr_products | es_products | fr_leaflets [limit] | es_leaflets [limit]
"""
from __future__ import annotations

import csv
import io
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import ROOT, Fetcher  # noqa: E402
from connectors.leaflets import html_to_lines, parse, write_sites  # noqa: E402
from models.db import SubstanceMatcher, add_gap, connect  # noqa: E402
from models.product_writer import ProductWriter  # noqa: E402

BDPM = "https://base-donnees-publique.medicaments.gouv.fr/download/file/"
CIMA = "https://cima.aemps.es/cima/rest/medicamentos"
PROC = {"Procédure centralisée": "centralised", "Procédure décentralisée": "DCP",
        "Procédure de reconnaissance mutuelle": "MRP", "Procédure nationale": "national"}


def existing(conn, prefix):
    return {k for (k,) in conn.execute("SELECT natural_key FROM product WHERE valid_to IS NULL AND natural_key LIKE %s",
                                       (prefix + "%",)).fetchall()}


def fr_products():
    with connect() as conn:
        def latest(name):
            return conn.execute("""SELECT r.path, r.raw_id FROM raw_object r JOIN source s USING (source_id)
                                   WHERE s.name='FR BDPM' AND r.url LIKE %s ORDER BY r.raw_id DESC LIMIT 1""",
                                (f"%{name}",)).fetchone()
        (pc, raw_cis), (pp, _) = latest("CIS_bdpm.txt"), latest("CIS_COMPO_bdpm.txt")
        subst = defaultdict(set)
        for row in csv.reader(io.StringIO((ROOT / pp).read_bytes().decode("latin-1")), delimiter="\t"):
            if len(row) >= 7 and row[6].strip() == "SA":
                subst[row[0]].add(f"{row[3]} {row[4]}".strip())
        have, m, w = existing(conn, "FR|CIS|"), SubstanceMatcher(conn), ProductWriter(conn, "FR BDPM")
        for row in csv.reader(io.StringIO((ROOT / pc).read_bytes().decode("latin-1")), delimiter="\t"):
            if len(row) < 11 or f"FR|CIS|{row[0]}" in have or row[4].strip() != "Autorisation active":
                continue
            s = " | ".join(sorted(subst.get(row[0], [])))
            w.write(f"FR|CIS|{row[0]}", dict(substances_raw=s[:1000] or None, name=row[1], country="FR",
                                             mah_raw=row[10].strip(), authorisation_no=row[0], form=row[2],
                                             procedure=PROC.get(row[5], row[5]), procedure_no=row[9] or None,
                                             product_status=f"{row[4]}; {row[6]}", is_veterinary=False),
                    m.match(s), s, BDPM + "CIS_bdpm.txt", raw_cis)
        print("FR full", dict(w.stats), flush=True)


def es_products():
    with connect() as conn:
        f = Fetcher(conn, "ES AEMPS CIMA REST")
        have, m, w = existing(conn, "ES|"), SubstanceMatcher(conn), ProductWriter(conn, "ES AEMPS CIMA REST")
        page = 1
        while True:
            r, raw_id = f.get(CIMA, params={"autorizados": 1, "pagina": page})
            if r.status_code != 200:
                add_gap(conn, "product", "source", "ES full", f"CIMA Liste Seite {page}: HTTP {r.status_code}", CIMA,
                        "ES AEMPS CIMA REST")
                break
            j = r.json()
            for it in j.get("resultados", []):
                if f"ES|{it['nregistro']}" in have:
                    continue
                vtm = (it.get("vtm") or {}).get("nombre", "")
                pl = next((d.get("urlHtml") or d.get("url") for d in it.get("docs", []) if d.get("tipo") == 2), None)
                w.write(f"ES|{it['nregistro']}",
                        dict(substances_raw=vtm or None, name=it["nombre"], country="ES", mah_raw=it.get("labtitular"),
                             authorisation_no=it["nregistro"], strength=it.get("dosis"),
                             form=(it.get("formaFarmaceutica") or {}).get("nombre"),
                             procedure="centralised" if it.get("ema") else None,
                             product_status="comercializado" if it.get("comerc") else "no comercializado",
                             is_veterinary=False, leaflet_url=pl),
                        m.match(f"{vtm} {it['nombre']}"), f"{vtm} {it['nombre']}", f"{CIMA}?nregistro={it['nregistro']}", raw_id)
            if page % 50 == 0:
                conn.commit()
                print("ES page", page, dict(w.stats), flush=True)
            if page * j.get("tamanioPagina", 25) >= j.get("totalFilas", 0):
                break
            page += 1
        print("ES full", dict(w.stats), flush=True)


def todo(conn, src):
    """products of a source without a current manufacturer row and without an open manufacturer gap"""
    return conn.execute("""SELECT p.product_id, p.authorisation_no, p.leaflet_url FROM product p
                           WHERE p.valid_to IS NULL AND p.source_name=%s
                             AND NOT EXISTS (SELECT 1 FROM product_manufacturer pm WHERE pm.product_id=p.product_id AND pm.valid_to IS NULL)
                             AND NOT EXISTS (SELECT 1 FROM gap g WHERE g.area='manufacturer' AND g.entity_ref=p.product_id::text
                                             AND g.resolved_at IS NULL)
                           ORDER BY p.product_id""", (src,)).fetchall()


def leaflets(country, limit=None):
    src = {"FR": "FR BDPM", "ES": "ES AEMPS CIMA REST"}[country]
    st = defaultdict(int)
    with connect() as conn:
        f = Fetcher(conn, src, raw_dir={"FR": "bdpm_leaflets", "ES": "cima_leaflets"}[country])
        for pid, no, pl in todo(conn, src)[:limit]:
            st["products"] += 1
            if country == "FR":
                url = f"https://base-donnees-publique.medicaments.gouv.fr/medicament/{no}/extrait"
                r, raw_id = f.get(url)
                lines = html_to_lines(r.text) if r.status_code == 200 else []
                idx = next((i for i, ln in enumerate(lines) if ln.lower().startswith("notice")), 0)
                sites, src_url, leaf = parse(lines[idx:], home_country="FR"), url, url + "#notice"
            else:
                api = "https://cima.aemps.es/cima/rest/docSegmentado/contenido/2"
                r, raw_id = f.get(api, params={"nregistro": no, "seccion": "6"})
                src_url, leaf, sites = f"{api}?nregistro={no}&seccion=6", pl or f"{api}?nregistro={no}&seccion=6", []
                if r.status_code == 200 and r.content:
                    try:
                        sites = parse(html_to_lines(" ".join(x.get("contenido", "") if isinstance(x, dict) else str(x)
                                                             for x in r.json())), home_country="ES")
                    except ValueError:
                        sites = []
            if not sites:
                st["gaps"] += 1
                add_gap(conn, "manufacturer", "product", pid,
                        f"{country}: Hersteller-Abschnitt in Packungsbeilage nicht gefunden (HTTP {r.status_code})", leaf, src)
            else:
                write_sites(conn, pid, sites, "batch_release", leaf, src_url, src, raw_id)
                st["with_sites"] += 1
                st["sites"] += len(sites)
            if st["products"] % 200 == 0:
                conn.commit()
                print(country, "leaflets", dict(st), flush=True)
    print(country, "leaflets done", dict(st), flush=True)


if __name__ == "__main__":
    fn, *a = sys.argv[1:]
    {"fr_products": fr_products, "es_products": es_products,
     "fr_leaflets": lambda *x: leaflets("FR", *map(int, x)), "es_leaflets": lambda *x: leaflets("ES", *map(int, x))}[fn](*a)
