"""Shared writer for `product` + `product_api` (versioned on natural_key)."""
from __future__ import annotations

from models.db import new_id, now, upsert_versioned

COMPARE = ["substances_raw", "name", "country", "mah_raw", "authorisation_no", "strength", "form", "procedure", "procedure_no",
           "product_status", "is_veterinary", "leaflet_url", "atc"]

COUNTRY = {
    "austria": "AT", "belgium": "BE", "bulgaria": "BG", "croatia": "HR", "cyprus": "CY", "czechia": "CZ",
    "czech republic": "CZ", "denmark": "DK", "estonia": "EE", "finland": "FI", "france": "FR", "germany": "DE",
    "greece": "GR", "hungary": "HU", "iceland": "IS", "ireland": "IE", "italy": "IT", "latvia": "LV",
    "liechtenstein": "LI", "lithuania": "LT", "luxembourg": "LU", "malta": "MT", "netherlands": "NL",
    "norway": "NO", "poland": "PL", "portugal": "PT", "romania": "RO", "slovakia": "SK", "slovenia": "SI",
    "spain": "ES", "sweden": "SE", "united kingdom": "GB", "united kingdom (northern ireland)": "XI",
    "european union": "EU",
}


class ProductWriter:
    def __init__(self, conn, source_name: str):
        self.conn, self.src = conn, source_name
        self.stats = dict(rows=0, new=0, changed=0, same=0, api_links=0)

    def write(self, natural_key: str, vals: dict, api_ids: list[int], substance_raw: str | None,
              source_url: str, raw_id: int | None, status: str = "official") -> int:
        row = self.conn.execute("SELECT product_id FROM product WHERE natural_key=%s AND valid_to IS NULL",
                                (natural_key,)).fetchone()
        pid = row[0] if row else new_id(self.conn)
        def clean(v):  # pandas NaN / 'nan' strings are missing values, never data
            if isinstance(v, float) and v != v:
                return None
            if isinstance(v, str) and v.strip().lower() in ("nan", "none", "null", ""):
                return None
            return v
        full = {k: clean(vals.get(k)) for k in COMPARE} | dict(natural_key=natural_key, source_url=source_url,
                                                        source_name=self.src, retrieved_at=now(), status=status,
                                                        raw_id=raw_id)
        res = upsert_versioned(self.conn, "product", "product_id", pid, full, COMPARE)
        self.stats["rows"] += 1
        self.stats[res] += 1
        for aid in api_ids:
            self.conn.execute("INSERT INTO product_api (product_id, api_id, substance_raw) VALUES (%s,%s,%s)"
                              " ON CONFLICT DO NOTHING", (pid, aid, (substance_raw or "")[:500]))
            self.stats["api_links"] += 1
        return pid
