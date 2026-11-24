"""Phase 8: sample verification against the LIVE primary source (not the raw store).

For N random rows per area the primary source is fetched again and the stored value must appear in it.
This is an automated re-check; a human spot check of the same sample is listed separately in the report.
"""
from __future__ import annotations

import html
import io
import json
import random
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import ROOT, client, throttle  # noqa: E402
from models.db import connect, norm_text  # noqa: E402

N = 50
_cache: dict[str, str] = {}


def text_of(url: str) -> str:
    if url in _cache:
        return _cache[url]
    c = client()
    throttle(url)
    r = c.get(url, timeout=180)
    ct = r.headers.get("content-type", "")
    if "pdf" in ct or url.endswith(".pdf"):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
            t.write(r.content)
            t.flush()
            txt = subprocess.run(["pdftotext", t.name, "-"], capture_output=True, text=True).stdout
    elif "zip" in ct:
        z = zipfile.ZipFile(io.BytesIO(r.content))
        txt = " ".join(z.read(n).decode("latin-1") for n in z.namelist())
    elif "spreadsheet" in ct or url.endswith(".xlsx"):
        import pandas as pd
        txt = " ".join(pd.read_excel(io.BytesIO(r.content), header=None, sheet_name=None, dtype=str)
                       [k].fillna("").astype(str).agg(" ".join, axis=1).str.cat(sep=" ") for k in
                       pd.ExcelFile(io.BytesIO(r.content)).sheet_names)
    else:
        try:
            txt = r.content.decode("utf-8")
        except UnicodeDecodeError:
            txt = r.content.decode("latin-1")
        txt = html.unescape(re.sub(r"<[^>]+>", " ", txt))
    _cache[url] = norm_text(re.sub(r"\s+", " ", txt))
    return _cache[url]


def contains(hay: str, needle: str | None) -> bool:
    if not needle:
        return True
    n = norm_text(re.sub(r"\s+", " ", str(needle)))
    return n in hay or n[:25] in hay


def run(seed=7):
    random.seed(seed)
    out = {}
    with connect() as conn:
        areas = {
            "product_manufacturer": conn.execute("""SELECT row_id, source_url, manufacturer_raw, site_country FROM product_manufacturer
                                                    WHERE valid_to IS NULL ORDER BY random() LIMIT %s""", (N,)).fetchall(),
            "product": conn.execute("""SELECT row_id, CASE WHEN source_name='US Drugs@FDA' THEN 'https://www.fda.gov/media/89850/download'
                                              WHEN source_name='FR BDPM' THEN 'https://base-donnees-publique.medicaments.gouv.fr/download/file/CIS_bdpm.txt'
                                              ELSE source_url END, name, mah_raw FROM product
                                       WHERE valid_to IS NULL AND source_name NOT LIKE 'EMA Article%%' ORDER BY random() LIMIT %s""", (N - 10,)).fetchall()
                       + conn.execute("""SELECT row_id, source_url, name, mah_raw FROM product WHERE valid_to IS NULL
                                         AND source_name LIKE 'EMA Article%%' ORDER BY random() LIMIT 10""").fetchall(),
            "api_certificate": conn.execute("""SELECT row_id, source_url, number, holder_raw FROM api_certificate WHERE valid_to IS NULL
                                               ORDER BY random() LIMIT %s""", (N,)).fetchall(),
        }
        for area, rows in areas.items():
            ok, fails = 0, []
            for rid, url, a, b in rows:
                try:
                    hay = text_of(url)
                except Exception as e:  # noqa: BLE001
                    fails.append(dict(row_id=rid, url=url, error=str(e)[:120]))
                    continue
                checks = [a] if area == "product_manufacturer" else [a, b]
                if all(contains(hay, x) for x in checks if not (area == "api_certificate" and x == a)) and \
                        (area != "api_certificate" or re.search(rf"\b{re.escape(str(a))}\b", hay)):
                    ok += 1
                else:
                    fails.append(dict(row_id=rid, url=url, value=[a, b]))
            out[area] = dict(sampled=len(rows), confirmed=ok, error_rate=round(1 - ok / max(len(rows), 1), 3), failures=fails[:10])
            print(area, out[area]["sampled"], "confirmed", ok, "error rate", out[area]["error_rate"], flush=True)
    (ROOT / "reports" / "verification_pilot.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return out


if __name__ == "__main__":
    run()
