"""API certificate connectors (pilot): FDA DMF list (type II = drug substance), WHO PQ APIs.

CEP (EDQM) and Written Confirmations (CDSCO) are not reachable -> gap per API.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher  # noqa: E402
from models.db import SubstanceMatcher, add_gap, connect, new_id, now, upsert_versioned  # noqa: E402

COMPARE = ["api_id", "holder_raw", "cert_type", "number", "cert_status", "issue_date", "substance_raw"]

# DMF subjects that mention the API but are NOT the API itself (intermediates, impurities, finished dosage forms)
NOT_API_RX = re.compile(r"interm[ie]+diate|\bside[- ]chain|\bfragment|impurit|tablets?\b|capsules?\b|injection|oral solution|suspension|"
                        r"\bstage\b|precursor|starting material|working standard|reference standard|"
                        r"\bkey\b|\bcrude\b|pellets|granules|premix|\bmix\b|blend", re.I)


def write_cert(conn, key, vals):
    row = conn.execute("SELECT row_id FROM api_certificate WHERE natural_key=%s AND valid_to IS NULL", (key,)).fetchone()
    cur = conn.execute(f"SELECT {', '.join(COMPARE)} FROM api_certificate WHERE natural_key=%s AND valid_to IS NULL",
                       (key,)).fetchone()
    if cur and all((a or None) == (vals.get(c) or None) for a, c in zip(cur, COMPARE)):
        return "same"
    if row:
        conn.execute("UPDATE api_certificate SET valid_to=now() WHERE row_id=%s", (row[0],))
    cols = ["natural_key"] + list(vals)
    conn.execute(f"INSERT INTO api_certificate ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                 [key] + list(vals.values()))
    return "changed" if row else "new"


def fda_dmf():
    page = "https://www.fda.gov/drugs/drug-master-files-dmfs/list-drug-master-files-dmfs"
    with connect() as conn:
        f = Fetcher(conn, "FDA DMF-Liste")
        p, _ = f.get(page)
        link = re.search(r'href="(/media/\d+/download[^"]*)"', p.text).group(1)
        url = "https://www.fda.gov" + link.replace("&amp;", "&")
        r, raw_id = f.get(url)
        df = pd.read_excel(io.BytesIO(r.content), header=1)
        df = df[df["TYPE"].astype(str).str.strip() == "II"]
        m = SubstanceMatcher(conn)
        stats = dict(type2_rows=len(df), matched=0, excluded_not_api=0, new=0, changed=0, same=0)
        for row in df.itertuples(index=False):
            subj = str(row.SUBJECT)
            ids = m.match(subj)
            if not ids:
                continue
            if NOT_API_RX.search(subj) or len(ids) > 1:
                stats["excluded_not_api"] += 1  # intermediate / dosage form / combination -> not an API supplier record
                continue
            stats["matched"] += 1
            dmf = str(int(row._0)) if isinstance(row._0, (int, float)) else str(row._0)
            res = write_cert(conn, f"US_DMF|{dmf}", dict(
                api_id=ids[0], holder_raw=str(row.HOLDER).strip(), cert_type="US_DMF", number=dmf,
                cert_status={"A": "active", "I": "inactive"}.get(str(row.STATUS).strip(), str(row.STATUS)),
                issue_date=pd.to_datetime(row._3).date() if pd.notna(row._3) else None, substance_raw=subj,
                source_url=url, source_name="FDA DMF-Liste", retrieved_at=now(), status="official", raw_id=raw_id))
            stats[res] += 1
        print("FDA DMF", stats)
        return stats


def who_pq():
    url = "https://extranet.who.int/prequal/medicines/prequalified/active-pharmaceutical-ingredients/export?page&_format=csv"
    with connect() as conn:
        f = Fetcher(conn, "WHO Prequalification APIs")
        r, raw_id = f.get(url)
        df = pd.read_csv(io.BytesIO(r.content))
        m = SubstanceMatcher(conn)
        stats = dict(rows=len(df), matched=0, new=0, changed=0, same=0)
        for row in df.itertuples(index=False):
            ids = m.match(row.INN)
            if not ids:
                continue
            stats["matched"] += 1
            res = write_cert(conn, f"WHO_PQ|{row[0]}", dict(
                api_id=ids[0], holder_raw=row.Applicant, cert_type="WHO_PQ", number=row[0], cert_status="prequalified",
                issue_date=pd.to_datetime(re.sub(r"\s+", " ", str(row[5])), errors="coerce").date()
                if pd.notna(row[5]) else None, substance_raw=row.INN,
                source_url="https://extranet.who.int/prequal/medicines/prequalified/active-pharmaceutical-ingredients",
                source_name="WHO Prequalification APIs", retrieved_at=now(), status="official", raw_id=raw_id))
            stats[res] += 1
        print("WHO PQ", stats)
        return stats


def gaps():
    with connect() as conn:
        for (inn,) in conn.execute("SELECT inn FROM api WHERE parent_api_id IS NULL AND valid_to IS NULL"):
            add_gap(conn, "certificate", "api", inn, "CEP nicht abrufbar (EDQM robots.txt/WAF) – Lizenzanfrage offen",
                    "EDQM Lizenz / manuelle Abfrage", "EDQM CEP-Datenbank")
            add_gap(conn, "certificate", "api", inn, "Written Confirmations nicht abrufbar (CDSCO blockiert)",
                    "Handbeschaffung cdsco.gov.in", "CDSCO Written Confirmations")


if __name__ == "__main__":
    fda_dmf()
    who_pq()
    gaps()
