"""Shortage connectors (pilot): EMA ESMP shortages report (central products), AEMPS CIMA psuministro (ES).
Each shortage -> event(type='shortage'), linked to API (entity_type='api')."""
from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher  # noqa: E402
from connectors.ema import read_xlsx  # noqa: E402
from models.db import SubstanceMatcher, connect, now  # noqa: E402


def _event(conn, aid, date, detail, url, src, raw_id):
    key = json.dumps(detail, sort_keys=True, default=str)
    if conn.execute("SELECT 1 FROM event WHERE event_type='shortage' AND entity_ref=%s AND detail::text=%s::jsonb::text"
                    " AND valid_to IS NULL", (aid, key)).fetchone():
        return 0
    conn.execute("""INSERT INTO event (event_type, event_date, entity_type, entity_ref, detail, source_url, source_name,
                    retrieved_at, status, raw_id) VALUES ('shortage',%s,'api',%s,%s::jsonb,%s,%s,%s,'official',%s)""",
                 (date, aid, key, url, src, now(), raw_id))
    return 1


def ema():
    url = "https://www.ema.europa.eu/en/documents/report/medicines-output-shortages-report_en.xlsx"
    with connect() as conn:
        f = Fetcher(conn, "EMA Shortages (ESMP)")
        r, raw_id = f.get(url)
        df = read_xlsx(r.content)
        m, n = SubstanceMatcher(conn), 0
        for _, row in df.iterrows():
            for aid in m.match(f"{row['International non-proprietary name (INN) or common name']} {row['Medicine affected']}"):
                n += _event(conn, aid, pd.to_datetime(row["Start of shortage date"], errors="coerce").date()
                            if pd.notna(row["Start of shortage date"]) else None,
                            dict(country="EU", product=row["Medicine affected"], state=row["Supply shortage status"],
                                 expected_resolution=str(row["Expected resolution date"]), forms=row["Pharmaceutical forms affected"]),
                            row["Shortage URL"], "EMA Shortages (ESMP)", raw_id)
        print("EMA shortages events:", n)


def cima():
    api = "https://cima.aemps.es/cima/rest/psuministro"
    with connect() as conn:
        f = Fetcher(conn, "ES AEMPS CIMA Engpässe")
        m, n, page = SubstanceMatcher(conn), 0, 1
        while True:
            r, raw_id = f.get(api, params={"pagina": page})
            j = r.json()
            for it in j.get("resultados", []):
                ids = m.match(it.get("nombre", ""))
                for aid in ids:
                    fini = it.get("fini")
                    n += _event(conn, aid, datetime.fromtimestamp(fini / 1000, timezone.utc).date() if fini else None,
                                dict(country="ES", product=it.get("nombre"), cn=it.get("cn"), active=it.get("activo"),
                                     type=it.get("tipoProblemaSuministro"), note=it.get("observ")),
                                f"https://cima.aemps.es/cima/publico/detalle.html?nregistro={it.get('nregistro')}",
                                "ES AEMPS CIMA Engpässe", raw_id)
            if page * j.get("tamanioPagina", 25) >= j.get("totalFilas", 0):
                break
            page += 1
        print("CIMA shortage events:", n, "pages:", page)


if __name__ == "__main__":
    ema()
    cima()
