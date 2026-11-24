"""EMA connectors: Article-57 product database (all EEA human products) + central medicines report.

Art. 57: columns 6-8 (PV system location, PV e-mail, PV phone) are dropped on read (GDPR rule: no contact data).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher  # noqa: E402
from models.db import SubstanceMatcher, add_gap, connect, norm_text  # noqa: E402
from models.product_writer import COUNTRY, ProductWriter  # noqa: E402

ART57_URL = "https://www.ema.europa.eu/en/documents/other/article-57-product-data_en.xlsx"
MED_URL = "https://www.ema.europa.eu/en/documents/report/medicines-output-medicines-report_en.xlsx"


def read_xlsx(content: bytes, min_cols: int = 5) -> pd.DataFrame:
    head = pd.read_excel(io.BytesIO(content), header=None, nrows=40)
    hdr = next(i for i in range(40) if head.iloc[i].notna().sum() >= min_cols)
    return pd.read_excel(io.BytesIO(content), header=hdr)


def art57():
    with connect() as conn:
        f = Fetcher(conn, "EMA Article-57-Datenbank")
        r, raw_id = f.get(ART57_URL)
        df = read_xlsx(r.content)
        df = df.iloc[:, :5]  # keep: product name, active substance, route, country, MAH  (drop PV contact columns)
        df.columns = ["name", "substance", "route", "country", "mah"]
        m, w = SubstanceMatcher(conn), ProductWriter(conn, "EMA Article-57-Datenbank")
        unmapped_country, agg = set(), {}
        for row in df.itertuples(index=False):
            ids = m.match(row.substance)
            if not ids:
                continue
            cc = COUNTRY.get(norm_text(row.country))
            if not cc:
                unmapped_country.add(row.country)
                continue
            key = f"ART57|{cc}|{norm_text(row.name)}|{norm_text(row.mah)}"
            a = agg.setdefault(key, dict(name=row.name, cc=cc, mah=row.mah, ids=set(), subst=set()))
            a["ids"].update(ids)
            a["subst"].add(str(row.substance))
        for key, a in agg.items():  # source has duplicate rows per key (case/route variants) -> one product
            w.write(key, dict(name=a["name"], country=a["cc"], mah_raw=a["mah"],
                              procedure="centralised" if a["cc"] == "EU" else None, is_veterinary=False),
                    sorted(a["ids"]), " || ".join(sorted(a["subst"])), ART57_URL, raw_id)
        for c in unmapped_country:
            add_gap(conn, "product", "country", c, "Art.57: Land nicht gemappt", None, "EMA Article-57-Datenbank")
        print("ART57", len(df), "rows in file;", w.stats, "unmapped countries:", unmapped_country)
        return w.stats


def central():
    with connect() as conn:
        f = Fetcher(conn, "EMA Medicine data download")
        r, raw_id = f.get(MED_URL)
        df = read_xlsx(r.content)
        m, w = SubstanceMatcher(conn), ProductWriter(conn, "EMA Medicine data download")
        for _, row in df.iterrows():
            subst = f"{row.get('International non-proprietary name (INN) / common name', '')} {row.get('Active substance', '')}"
            ids = m.match(subst)
            if not ids:
                continue
            vet = str(row["Category"]).lower().startswith("vet")
            atc = row.get("ATCvet code (veterinary)") if vet else row.get("ATC code (human)")
            w.write(f"EMA|{row['EMA product number']}",
                    dict(name=row["Name of medicine"], country="EU",
                         mah_raw=row["Marketing authorisation developer / applicant / holder"],
                         authorisation_no=row["EMA product number"], procedure="centralised",
                         procedure_no=row["EMA product number"], product_status=row["Medicine status"],
                         is_veterinary=vet, leaflet_url=row["Medicine URL"],
                         atc=None if pd.isna(atc) else str(atc)),
                    ids, subst, row["Medicine URL"], raw_id)
        print("EMA central", len(df), "rows in file;", w.stats)
        return w.stats


if __name__ == "__main__":
    central()
    art57()
