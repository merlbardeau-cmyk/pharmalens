"""NL CBG-MEB: products from the official metadata.csv + manufacturers from the patient leaflet (bijsluiter) PDF.

robots.txt only disallows /Documents/SmPC/*; leaflets under /bijsluiters/ are allowed.
Parallel imports (registration number contains '//') list importer/repackager -> gap, never manufacturer.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher  # noqa: E402
from connectors.leaflets import pdf_lines, write_sites  # noqa: E402
from enrich.leaflet_parser import parse  # noqa: E402
from models.db import SubstanceMatcher, add_gap, connect  # noqa: E402
from models.product_writer import ProductWriter  # noqa: E402

SRC = "NL CBG Geneesmiddeleninformatiebank"
META = "https://www.geneesmiddeleninformatiebank.nl/metadata.csv"


def run(limit=None):
    st = dict(products=0, leaflets=0, with_sites=0, sites=0, gaps=0, parallel=0, no_leaflet=0)
    with connect() as conn:
        f = Fetcher(conn, SRC, raw_dir="cbg")
        r, raw_id = f.get(META)
        rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8")), delimiter="|"))
        m, w = SubstanceMatcher(conn), ProductWriter(conn, SRC)
        todo = []
        for row in rows:
            ids = m.match(row["WERKZAMESTOFFEN"])
            if not ids:
                continue
            reg = row["REGISTRATIENUMMER"].strip()
            soort = row["SOORT"].strip() or ("EU" if reg.upper().startswith("EU") else "")
            parallel = "//" in reg
            pid = w.write(f"NL|{reg}|{row['PRODUCTNAAM'].strip().lower()}", dict(
                name=row["PRODUCTNAAM"], country="NL", mah_raw=row["HANDELSVERGUNNINGHOUDER"].strip(),
                authorisation_no=f"{soort} {reg}".strip(), strength=row["POTENTIE"] or None, form=row["FARMACEUTISCHEVORM"],
                procedure="parallel import" if parallel else (row["PROCEDURENUMMER"] and "DCP/MRP") or ("centralised" if soort == "EU" else "national"),
                procedure_no=row["PROCEDURENUMMER"] or None, product_status=row["AFLEVERSTATUS"], is_veterinary=False,
                leaflet_url=row["BIJSLUITER_FILENAAM"] or None, atc=(row["ATC"] or "").split(" - ")[0] or None),
                ids, row["WERKZAMESTOFFEN"], row["PRODUCTDETAIL_LINK"] or META, raw_id)
            st["products"] += 1
            if parallel:
                st["parallel"] += 1
                add_gap(conn, "manufacturer", "product", pid, "NL Parallelimport: Bijsluiter nennt Importeur/Umpacker – bewusst nicht als Hersteller übernommen",
                        row["BIJSLUITER_FILENAAM"], SRC)
            elif not row["BIJSLUITER_FILENAAM"]:
                st["no_leaflet"] += 1
                add_gap(conn, "manufacturer", "product", pid, "NL: keine Bijsluiter-Datei im CBG-Register (z. B. EU-zentral → EMA Annex IIA)",
                        row["PRODUCTDETAIL_LINK"], SRC)
            else:
                todo.append((pid, row["BIJSLUITER_FILENAAM"]))
        for pid, url in todo[:limit]:
            pr, praw = f.get(url)
            st["leaflets"] += 1
            sites = parse(pdf_lines(pr.content), home_country="NL") if pr.status_code == 200 and pr.content[:4] == b"%PDF" else []
            if not sites:
                st["gaps"] += 1
                add_gap(conn, "manufacturer", "product", pid, f"NL: Fabrikant-Sektion im Bijsluiter nicht gefunden (HTTP {pr.status_code})", url, SRC)
                continue
            write_sites(conn, pid, sites, "batch_release", url, url, SRC, praw)
            st["with_sites"] += 1
            st["sites"] += len(sites)
        print("NL CBG", st, "products written:", w.stats, flush=True)
        return st


if __name__ == "__main__":
    run(*(int(a) for a in sys.argv[1:]))
