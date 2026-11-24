"""US Orange Book -> patent (+ exclusivity as event). Patent type rules (FDA flags):
  Drug_Substance_Flag=Y -> 'substance' ; Drug_Product_Flag=Y -> 'formulation' ; only use code -> 'use'.
Patents listed on combination products are tagged 'on_combination' so a combo's formulation patent never
counts as protection of a single API (brief requirement). LoE per API uses mono-product listings first.
"""
from __future__ import annotations

import csv
import io
import sys
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher  # noqa: E402
from models.db import SubstanceMatcher, add_gap, connect, now  # noqa: E402

URL = "https://www.fda.gov/media/76860/download"


def run():
    with connect() as conn:
        f = Fetcher(conn, "US Orange Book")
        r, raw_id = f.get(URL)
        z = zipfile.ZipFile(io.BytesIO(r.content))

        def tab(n):
            return list(csv.DictReader(io.StringIO(z.read(n).decode("latin-1")), delimiter="~"))
        m = SubstanceMatcher(conn)
        prod = {}
        for p in tab("products.txt"):
            ids = m.match(p["Ingredient"])
            if ids:
                n_ingr = len([x for x in p["Ingredient"].split(";") if x.strip()])
                prod[(p["Appl_Type"], p["Appl_No"], p["Product_No"])] = (ids, n_ingr, p)
        agg = defaultdict(lambda: dict(products=set(), substance=False, product=False, use=set(), expiry=None,
                                       combo_only=True, delist=False))
        for pt in tab("patent.txt"):
            k = (pt["Appl_Type"], pt["Appl_No"], pt["Product_No"])
            if k not in prod:
                continue
            ids, n_ingr, p = prod[k]
            exp = datetime.strptime(pt["Patent_Expire_Date_Text"], "%b %d, %Y").date()
            for aid in ids:
                a = agg[(aid, pt["Patent_No"])]
                a["products"].add(f"{p['Appl_Type']}{p['Appl_No']}/{p['Product_No']} {p['Trade_Name']} ({p['Ingredient']})")
                a["substance"] |= pt["Drug_Substance_Flag"] == "Y"
                a["product"] |= pt["Drug_Product_Flag"] == "Y"
                if pt["Patent_Use_Code"]:
                    a["use"].add(pt["Patent_Use_Code"])
                a["expiry"] = max(filter(None, [a["expiry"], exp]))
                a["combo_only"] &= n_ingr > 1
                a["delist"] |= pt["Delist_Flag"] == "Y"
        conn.execute("UPDATE patent SET valid_to=now() WHERE jurisdiction='US' AND source_name='US Orange Book' AND valid_to IS NULL")
        n = 0
        for (aid, no), a in agg.items():
            ptype = "substance" if a["substance"] else "formulation" if a["product"] else "use"
            if a["combo_only"]:
                ptype += "_on_combination"
            conn.execute(
                """INSERT INTO patent (api_id, number, jurisdiction, patent_type, expiry, patent_status, legal_events,
                       source_url, source_name, retrieved_at, status, raw_id)
                   VALUES (%s,%s,'US',%s,%s,%s,%s,%s,'US Orange Book',%s,'official',%s)""",
                (aid, f"US{no}", ptype, a["expiry"], "delist requested" if a["delist"] else "listed",
                 __import__("json").dumps(dict(listed_on=sorted(a["products"]), use_codes=sorted(a["use"]))),
                 URL, now(), raw_id))
            n += 1
        for (inn,) in conn.execute("SELECT inn FROM api WHERE parent_api_id IS NULL AND valid_to IS NULL"):
            add_gap(conn, "patent", "api", inn, "EU/CH/UK-Patente und SPC: EPO-OPS-Key fehlt; nationale SPC-Register nicht angebunden",
                    "EPO OPS (Key), DPMA, INPI, UKIPO, IGE", "EPO OPS")
        print("Orange Book patents:", n)
        return n


if __name__ == "__main__":
    run()
