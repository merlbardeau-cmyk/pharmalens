"""Backfill product.auth_date from the raw store (no network). Only fills empty values; the source field is recorded.

FR BDPM (CIS_bdpm col 8), ES CIMA (estado.aut), CH Swissmedic (Zul.datum Dosisstärke), NL CBG (INSCHRIJVINGSDATUM),
US Drugs@FDA (Submissions ORIG approval), EMA central (Marketing authorisation date).
AT BASG, DK DKMA, IT AIFA and EMA Art. 57 publish no authorisation date in the data used -> stays empty (gap).
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import ROOT  # noqa: E402
from models.db import add_gap, connect  # noqa: E402


def latest(conn, source, like=""):
    return conn.execute("""SELECT r.path, r.url FROM raw_object r JOIN source s USING (source_id)
                           WHERE s.name=%s AND r.url LIKE %s ORDER BY r.raw_id""", (source, f"%{like}%")).fetchall()


def setd(conn, key_like, d, field, exact=True):
    if not d:
        return 0
    q = ("UPDATE product SET auth_date=%s, auth_date_source=%s WHERE valid_to IS NULL AND auth_date IS NULL AND "
         + ("natural_key=%s" if exact else "natural_key LIKE %s"))
    return conn.execute(q, (d, field, key_like)).rowcount


def run():
    st = {}
    with connect() as conn:
        # FR
        n = 0
        for path, _ in latest(conn, "FR BDPM", "CIS_bdpm.txt")[-1:]:
            for row in csv.reader(io.StringIO((ROOT / path).read_bytes().decode("latin-1")), delimiter="\t"):
                if len(row) > 7 and row[7]:
                    try:
                        n += setd(conn, f"FR|CIS|{row[0]}", datetime.strptime(row[7].strip(), "%d/%m/%Y").date(), "BDPM: date AMM")
                    except ValueError:
                        pass
        st["FR"] = n
        # ES (CIMA list pages)
        n = 0
        for path, url in latest(conn, "ES AEMPS CIMA REST", "/medicamentos?"):
            try:
                j = json.loads((ROOT / path).read_text())
            except ValueError:
                continue
            for it in j.get("resultados", []):
                ms = (it.get("estado") or {}).get("aut")
                if ms:
                    n += setd(conn, f"ES|{it['nregistro']}", datetime.fromtimestamp(ms / 1000, timezone.utc).date(), "CIMA: estado.aut")
        st["ES"] = n
        # CH
        n = 0
        for path, url in latest(conn, "CH Swissmedic Listen"):
            if not path.endswith(".xlsx"):
                continue
            raw = (ROOT / path).read_bytes()
            head = pd.read_excel(io.BytesIO(raw), header=None, nrows=10)
            hdr = next((i for i in range(10) if head.iloc[i].notna().sum() >= 8), None)
            if hdr is None:
                continue
            df = pd.read_excel(io.BytesIO(raw), header=hdr)
            df.columns = [str(c).split("\n")[0].strip() for c in df.columns]
            if "Zul.datum Dosisstärke" not in df.columns:
                continue
            for _, r in df.drop_duplicates(["Zulassungs-nummer", "Dosisstärke-nummer"]).iterrows():
                dd = r["Zul.datum Dosisstärke"]
                if pd.notna(dd):
                    n += setd(conn, f"CH|{r['Zulassungs-nummer']}|{r['Dosisstärke-nummer']}", pd.to_datetime(dd).date(), "Swissmedic: Zul.datum Dosisstärke")
        st["CH"] = n
        # NL
        n = 0
        for path, _ in latest(conn, "NL CBG Geneesmiddeleninformatiebank", "metadata.csv")[-1:]:
            for row in csv.DictReader(io.StringIO((ROOT / path).read_bytes().decode("utf-8")), delimiter="|"):
                ds = (row.get("INSCHRIJVINGSDATUM") or "").strip()
                if ds:
                    try:
                        n += setd(conn, f"NL|{row['REGISTRATIENUMMER'].strip()}|{row['PRODUCTNAAM'].strip().lower()}",
                                  datetime.strptime(ds, "%Y/%m/%d").date(), "CBG: INSCHRIJVINGSDATUM")
                    except ValueError:
                        pass
        st["NL"] = n
        # US
        n = 0
        for path, _ in latest(conn, "US Drugs@FDA")[-1:]:
            z = zipfile.ZipFile(io.BytesIO((ROOT / path).read_bytes()))
            orig = {}
            for s in csv.DictReader(io.StringIO(z.read("Submissions.txt").decode("latin-1")), delimiter="\t"):
                if s.get("SubmissionType") == "ORIG" and s.get("SubmissionStatus") == "AP" and s.get("SubmissionStatusDate"):
                    orig[s["ApplNo"]] = s["SubmissionStatusDate"][:10]
            for appl, ds in orig.items():
                n += setd(conn, f"US|%{appl}|%", date.fromisoformat(ds), "Drugs@FDA: ORIG approval", exact=False)
        st["US"] = n
        # EMA central
        n = 0
        for path, _ in latest(conn, "EMA Medicine data download", "medicines-output-medicines-report")[-1:]:
            raw = (ROOT / path).read_bytes()
            head = pd.read_excel(io.BytesIO(raw), header=None, nrows=40)
            hdr = next(i for i in range(40) if head.iloc[i].notna().sum() >= 5)
            df = pd.read_excel(io.BytesIO(raw), header=hdr)
            for _, r in df.iterrows():
                dd = r.get("Marketing authorisation date")
                if pd.notna(dd):
                    n += setd(conn, f"EMA|{r['EMA product number']}", pd.to_datetime(dd).date(), "EMA: Marketing authorisation date")
        st["EU"] = n
        cov = conn.execute("""SELECT country, count(*), count(auth_date) FROM product WHERE valid_to IS NULL GROUP BY 1
                              HAVING count(auth_date) > 0 OR country IN ('AT','DK','IT','DE') ORDER BY 2 DESC""").fetchall()
        for cc in ("AT", "DK", "IT"):
            add_gap(conn, "product", "source", f"auth_date {cc}", f"{cc}: Register liefert im genutzten Export kein Zulassungsdatum",
                    None, "enrich/auth_dates.py")
        add_gap(conn, "product", "source", "auth_date ART57", "EMA Art.-57-Datei enthält kein Zulassungsdatum", None, "enrich/auth_dates.py")
        print("auth_date filled", st)
        print("coverage", cov)


if __name__ == "__main__":
    run()
