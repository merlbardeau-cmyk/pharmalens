"""DB helpers: connection, id allocation, versioned (SCD2) writes, substance matching, gaps."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

from connectors.common import DSN

PROV = ("source_url", "source_name", "retrieved_at", "status", "raw_id")


def connect() -> psycopg.Connection:
    conn = psycopg.connect(DSN, autocommit=True)
    conn.execute("CREATE SEQUENCE IF NOT EXISTS entity_seq")
    return conn


def new_id(conn) -> int:
    return conn.execute("SELECT nextval('entity_seq')").fetchone()[0]


def now() -> datetime:
    return datetime.now(timezone.utc)


def norm_text(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.lower()).strip()


def _adapt(v):
    return Jsonb(v) if isinstance(v, dict) else v


def upsert_versioned(conn, table: str, key_col: str, key, values: dict, compare: list[str]) -> str:
    """Insert a new version only if a compared field changed. Returns 'new' | 'changed' | 'same'."""
    cur = conn.execute(f"SELECT row_id, {', '.join(compare)} FROM {table} WHERE {key_col}=%s AND valid_to IS NULL",
                       (key,)).fetchone()
    if cur is not None:
        old = dict(zip(compare, cur[1:]))
        if all(_eq(old[c], values.get(c)) for c in compare):
            return "same"
        conn.execute(f"UPDATE {table} SET valid_to=now() WHERE row_id=%s", (cur[0],))
    cols = [key_col] + list(values)
    conn.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                 [key] + [_adapt(values[c]) for c in values])
    return "new" if cur is None else "changed"


def _eq(a, b) -> bool:
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return list(a) == list(b)
    return (a or None) == (b or None)


def add_gap(conn, area: str, entity_type: str, entity_ref, reason: str, where: str | None = None, source: str | None = None):
    exists = conn.execute("SELECT 1 FROM gap WHERE area=%s AND entity_ref=%s AND reason=%s AND resolved_at IS NULL",
                          (area, str(entity_ref), reason)).fetchone()
    if not exists:
        conn.execute("INSERT INTO gap (area, entity_type, entity_ref, reason, where_obtainable, source_name)"
                     " VALUES (%s,%s,%s,%s,%s,%s)", (area, entity_type, str(entity_ref), reason, where, source))


class SubstanceMatcher:
    """Maps free-text substance strings to pilot api_ids (base API; salt detection kept as raw text)."""

    def __init__(self, conn):
        from models.pilot import PILOT
        rows = conn.execute("SELECT api_id, inn FROM api WHERE valid_to IS NULL AND parent_api_id IS NULL").fetchall()
        ids = {inn: aid for aid, inn in rows}
        self.rules = [(ids[inn], re.compile(r"(?<![a-z])(?:" + rx + ")")) for inn, _, rx in PILOT if inn in ids]

    def match(self, text: str | None) -> list[int]:
        t = norm_text(text)
        return [aid for aid, rx in self.rules if rx.search(t)]
