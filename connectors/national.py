"""National register connectors (pilot): FR BDPM, ES CIMA, CH Swissmedic (HAM+TAM), IT AIFA, US Drugs@FDA.

One function per source; each: download -> raw store -> parse -> map to product/product_api.
"""
from __future__ import annotations

import csv
import io
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher  # noqa: E402
from models.db import SubstanceMatcher, add_gap, connect, norm_text  # noqa: E402
from models.product_writer import ProductWriter  # noqa: E402

CIMA_ES = {"metformin": "metformina", "atorvastatin": "atorvastatina", "amlodipine": "amlodipino",
           "omeprazole": "omeprazol", "levothyroxine": "levotiroxina", "pyridostigmine": "piridostigmina",
           "dapsone": "dapsona", "fludrocortisone": "fludrocortisona", "mexiletine": "mexiletina",
           "hydroxycarbamide": "hidroxicarbamida", "apixaban": "apixaban", "empagliflozin": "empagliflozina",
           "sacubitril": "sacubitrilo", "edoxaban": "edoxaban", "semaglutide": "semaglutida"}


# ------------------------------------------------------------------------------------------- FR
def bdpm():
    base = "https://base-donnees-publique.medicaments.gouv.fr/download/file/"
    with connect() as conn:
        f = Fetcher(conn, "FR BDPM")
        rc, raw_cis = f.get(base + "CIS_bdpm.txt")
        rp, raw_compo = f.get(base + "CIS_COMPO_bdpm.txt")
        m, w = SubstanceMatcher(conn), ProductWriter(conn, "FR BDPM")
        subst = defaultdict(set)
        for row in csv.reader(io.StringIO(rp.content.decode("latin-1")), delimiter="\t"):
            if len(row) >= 7 and row[6].strip() == "SA":
                subst[row[0]].add(f"{row[3]} {row[4]}".strip())
        n = 0
        for row in csv.reader(io.StringIO(rc.content.decode("latin-1")), delimiter="\t"):
            if len(row) < 11:
                continue
            s = " | ".join(sorted(subst.get(row[0], [])))
            ids = m.match(s)
            if not ids:
                continue
            proc = {"Procédure centralisée": "centralised", "Procédure décentralisée": "DCP",
                    "Procédure de reconnaissance mutuelle": "MRP", "Procédure nationale": "national"}.get(row[5], row[5])
            w.write(f"FR|CIS|{row[0]}", dict(name=row[1], country="FR", mah_raw=row[10].strip(), authorisation_no=row[0],
                                             form=row[2], procedure=proc, procedure_no=row[9] or None,
                                             product_status=f"{row[4]}; {row[6]}", is_veterinary=False),
                    ids, s, base + "CIS_bdpm.txt", raw_cis)
            n += 1
        print("FR BDPM", w.stats)
        return w.stats


# ------------------------------------------------------------------------------------------- ES
def cima():
    api = "https://cima.aemps.es/cima/rest/medicamentos"
    with connect() as conn:
        f = Fetcher(conn, "ES AEMPS CIMA REST")
        m, w = SubstanceMatcher(conn), ProductWriter(conn, "ES AEMPS CIMA REST")
        for inn, es in CIMA_ES.items():
            page = 1
            while True:
                r, raw_id = f.get(api, params={"practiv1": es, "pagina": page})
                if r.status_code != 200:
                    add_gap(conn, "product", "api", inn, f"CIMA HTTP {r.status_code}", api, "ES AEMPS CIMA REST")
                    break
                j = r.json()
                for it in j.get("resultados", []):
                    text = f"{(it.get('vtm') or {}).get('nombre', '')} {it['nombre']}"
                    ids = m.match(text)
                    if not ids:
                        continue
                    pl = next((d.get("urlHtml") or d.get("url") for d in it.get("docs", []) if d.get("tipo") == 2), None)
                    w.write(f"ES|{it['nregistro']}",
                            dict(name=it["nombre"], country="ES", mah_raw=it.get("labtitular"),
                                 authorisation_no=it["nregistro"], strength=it.get("dosis"),
                                 form=(it.get("formaFarmaceutica") or {}).get("nombre"),
                                 procedure="centralised" if it.get("ema") else None,
                                 product_status="comercializado" if it.get("comerc") else "no comercializado",
                                 is_veterinary=False, leaflet_url=pl),
                            ids, text, f"{api}?nregistro={it['nregistro']}", raw_id)
                if page * j.get("tamanioPagina", 25) >= j.get("totalFilas", 0):
                    break
                page += 1
        add_gap(conn, "product", "source", "ES veterinary", "Tierarzneimittel ES nur in CIMAVet (Host nicht freigegeben)",
                "cimavet.aemps.es", "ES AEMPS CIMA REST")
        print("ES CIMA", w.stats)
        return w.stats


# ------------------------------------------------------------------------------------------- CH
def swissmedic():
    base = "https://www.swissmedic.ch/dam/swissmedic/de/dokumente/internetlisten/"
    files = {False: base + "zugelassene_packungen_human.xlsx.download.xlsx/zugelassene_packungen_ham.xlsx",
             True: base + "zugelassene_verpackungen_tam.xlsx.download.xlsx/Zugelassene_Packungen%20TAM.xlsx"}
    with connect() as conn:
        f = Fetcher(conn, "CH Swissmedic Listen")
        m, w = SubstanceMatcher(conn), ProductWriter(conn, "CH Swissmedic Listen")
        for vet, url in files.items():
            r, raw_id = f.get(url)
            head = pd.read_excel(io.BytesIO(r.content), header=None, nrows=10)
            hdr = next(i for i in range(10) if head.iloc[i].notna().sum() >= 8)
            df = pd.read_excel(io.BytesIO(r.content), header=hdr)
            df.columns = [str(c).split("\n")[0].strip() for c in df.columns]
            name_col = "Bezeichnung des Tierarzneimittels" if vet else "Bezeichnung des Arzneimittels"
            atc_col = "ATCvet-Code" if vet else "ATC-Code"
            done = set()
            for _, row in df.iterrows():
                key = f"CH|{row['Zulassungs-nummer']}|{row['Dosisstärke-nummer']}"
                if key in done:
                    continue  # one product per authorisation number + dosage strength (packages collapsed)
                ids = m.match(str(row["Wirkstoff(e)"]))
                if not ids:
                    continue
                done.add(key)
                w.write(key, dict(name=row[name_col], country="CH", mah_raw=row["Zulassungsinhaberin"],
                                  authorisation_no=f"{row['Zulassungs-nummer']}-{row['Dosisstärke-nummer']}",
                                  procedure="national", product_status=str(row["Gültigkeitsdauer der Zulassung *"]),
                                  is_veterinary=vet, atc=row.get(atc_col)),
                        ids, str(row["Wirkstoff(e)"]), url, raw_id)
        print("CH Swissmedic", w.stats)
        return w.stats


# ------------------------------------------------------------------------------------------- IT
def aifa():
    urls = ["https://www.aifa.gov.it/documents/20142/3815901/Classe-A_per_principio-attivo_30-6-2026.csv",
            "https://www.aifa.gov.it/documents/20142/3815901/Classe-H_per_principio-attivo_30-6-2026.csv"]
    with connect() as conn:
        f = Fetcher(conn, "IT AIFA Open Data")
        m, w = SubstanceMatcher(conn), ProductWriter(conn, "IT AIFA Open Data")
        seen = set()  # same AIC can appear in class A and H lists -> first occurrence wins within a run
        for url in urls:
            r, raw_id = f.get(url)
            rows = list(csv.reader(io.StringIO(r.content.decode("latin-1")), delimiter=";"))[1:]
            for row in rows:
                if len(row) < 6:
                    continue
                ids = m.match(row[0])
                if not ids:
                    continue
                aic = row[5].strip().zfill(9)
                if aic[:6] in seen:
                    continue
                seen.add(aic[:6])
                w.write(f"IT|AIC|{aic[:6]}", dict(name=row[2].split("*")[0].strip(), country="IT", mah_raw=row[4].strip(),
                                                  authorisation_no=aic[:6], procedure=None,
                                                  product_status="rimborsato " + url.split("Classe-")[1][0],
                                                  is_veterinary=False),
                        ids, row[0], url, raw_id)
        add_gap(conn, "product", "source", "IT non-reimbursed", "AIFA-Listen enthalten nur erstattete Arzneimittel (Klasse A/H)",
                "medicinali.aifa.gov.it (HTML)", "IT AIFA Open Data")
        print("IT AIFA", w.stats)
        return w.stats


# ------------------------------------------------------------------------------------------- US
def drugsfda():
    url = "https://www.fda.gov/media/89850/download"
    with connect() as conn:
        f = Fetcher(conn, "US Drugs@FDA")
        r, raw_id = f.get(url)
        z = zipfile.ZipFile(io.BytesIO(r.content))

        def tab(name):
            return list(csv.DictReader(io.StringIO(z.read(name).decode("latin-1")), delimiter="\t"))
        apps = {a["ApplNo"]: a for a in tab("Applications.txt")}
        status = {(s["ApplNo"], s["ProductNo"]): s["MarketingStatusID"] for s in tab("MarketingStatus.txt")}
        st_name = {"1": "Prescription", "2": "Over-the-counter", "3": "Discontinued", "4": "None (Tentative Approval)"}
        m, w = SubstanceMatcher(conn), ProductWriter(conn, "US Drugs@FDA")
        for p in tab("Products.txt"):
            ids = m.match(p["ActiveIngredient"])
            if not ids:
                continue
            a = apps.get(p["ApplNo"], {})
            w.write(f"US|{a.get('ApplType', '')}{p['ApplNo']}|{p['ProductNo']}",
                    dict(name=p["DrugName"], country="US", mah_raw=a.get("SponsorName"),
                         authorisation_no=f"{a.get('ApplType', '')} {p['ApplNo']}/{p['ProductNo']}", strength=p["Strength"],
                         form=p["Form"], procedure=a.get("ApplType"),
                         product_status=st_name.get(status.get((p["ApplNo"], p["ProductNo"])), "unknown"),
                         is_veterinary=False),
                    ids, p["ActiveIngredient"],
                    f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={p['ApplNo']}",
                    raw_id)
        add_gap(conn, "product", "source", "US veterinary", "Tierarzneimittel US (FDA Green Book) noch nicht angebunden",
                "fda.gov Green Book", "US Drugs@FDA")
        print("US Drugs@FDA", w.stats)
        return w.stats


if __name__ == "__main__":
    for fn in sys.argv[1:] or ["bdpm", "swissmedic", "aifa", "drugsfda", "cima"]:
        globals()[fn]()
