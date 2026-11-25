"""TED API v3 -> tender (contract award notices since 2023 that mention the API in full text).
The notice-to-API link means 'notice text mentions the API'; winner_raw is NOT attributed to the API lot
(multi-lot hospital tenders) -> winner_company_id stays empty until lot-level parsing (Phase 2)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher  # noqa: E402
from models.db import connect, now  # noqa: E402

API = "https://api.ted.europa.eu/v3/notices/search"
ISO3 = {"AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY", "CZE": "CZ", "DNK": "DK", "EST": "EE", "FIN": "FI", "FRA": "FR",
        "DEU": "DE", "GRC": "GR", "HUN": "HU", "IRL": "IE", "ITA": "IT", "LVA": "LV", "LTU": "LT", "LUX": "LU", "MLT": "MT", "NLD": "NL",
        "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK", "SVN": "SI", "ESP": "ES", "SWE": "SE", "NOR": "NO", "ISL": "IS", "LIE": "LI",
        "CHE": "CH", "GBR": "GB"}
FIELDS = ["publication-number", "notice-type", "buyer-name", "buyer-country", "winner-name", "publication-date",
          "total-value", "total-value-cur"]


def first(v):
    if isinstance(v, dict):
        v = next(iter(v.values()), None)
    if isinstance(v, list):
        return v[0] if v else None
    return v


def run():
    with connect() as conn:
        f = Fetcher(conn, "TED API v3")
        stats = {}
        for aid, inn in conn.execute("SELECT api_id, inn FROM api WHERE parent_api_id IS NULL AND valid_to IS NULL").fetchall():
            q = f'FT~"{inn}" AND notice-type IN (can-standard can-modif can-social) AND publication-date>=20230101'
            r, raw_id = f.get(API, method="POST", json={"query": q, "fields": FIELDS, "limit": 100, "scope": "ALL"})
            notices = r.json().get("notices", []) if r.status_code == 200 else []
            for nt in notices:
                pub = nt["publication-number"]
                if conn.execute("SELECT 1 FROM tender WHERE notice_id=%s AND api_id=%s", (pub, aid)).fetchone():
                    continue
                cc = first(nt.get("buyer-country"))
                val = first(nt.get("total-value"))
                conn.execute(
                    """INSERT INTO tender (api_id, country, buyer, winner_raw, value, currency, award_date, notice_id,
                           source_url, source_name, retrieved_at, status, raw_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'TED API v3',%s,'official',%s)""",
                    (aid, ISO3.get(cc), (first(nt.get("buyer-name")) or "") + (f" [{cc}]" if cc else ""), "; ".join(sorted({w for v in (nt.get("winner-name") or {}).values() for w in v}))
                     if isinstance(nt.get("winner-name"), dict) else None,
                     float(val) if val not in (None, "") else None, first(nt.get("total-value-cur")),
                     (nt.get("publication-date") or "")[:10] or None, pub, f"https://ted.europa.eu/en/notice/-/detail/{pub}",
                     now(), raw_id))
            stats[inn] = (r.json().get("totalNoticeCount") if r.status_code == 200 else f"HTTP {r.status_code}", len(notices))
        print("TED", stats)


if __name__ == "__main__":
    run()
