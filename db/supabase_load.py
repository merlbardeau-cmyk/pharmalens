"""Load the local PharmaLens DB into Supabase via the Management API (HTTPS only; token injected by proxy).

Steps: schema -> RLS on every table -> data in chunks -> row-count reconciliation.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import time
from pathlib import Path

import httpx

REF = "kulodmfvlxocvpkyyoiw"
URL = f"https://api.supabase.com/v1/projects/{REF}/database/query"
ROOT = Path(__file__).resolve().parents[1]
c = httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0), verify="/root/.ccr/ca-bundle.crt",
                 headers={"Authorization": "Bearer proxy-injected", "Content-Type": "application/json"})


def q(sql: str, retries: int = 4):
    for a in range(retries):
        r = c.post(URL, content=json.dumps({"query": sql}))
        if r.status_code in (200, 201):
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504) and a < retries - 1:
            time.sleep(10 * (a + 1))
            continue
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")


def clean(sql: str) -> str:
    sql = re.sub(r"^\\.*$", "", sql, flags=re.M)  # psql meta-commands (\restrict, \unrestrict)
    sql = re.sub(r"^(CREATE SCHEMA public;|COMMENT ON SCHEMA public IS .*;)$", "", sql, flags=re.M)  # exists in Supabase
    return re.sub(r"^SELECT pg_catalog.set_config\('search_path', '', false\);$", "", sql, flags=re.M)


def statements(sql: str):
    """split pg_dump output on ';' at line end outside dollar-quotes"""
    out, cur, in_dollar = [], [], False
    for line in sql.splitlines():
        if line.startswith("--") and not cur:
            continue
        cur.append(line)
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        if not in_dollar and line.rstrip().endswith(";"):
            s = "\n".join(cur).strip()
            if s:
                out.append(s)
            cur = []
    return out


def main(step: str):
    if step == "check":
        print(q("select count(*) n from information_schema.tables where table_schema='public'"))
    elif step == "schema":
        sql = clean((ROOT / "db" / "schema_dump.sql").read_text()).replace("public.gin_trgm_ops", "extensions.gin_trgm_ops")
        q("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions; CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA extensions;")
        q(sql)
        tables = [r["tablename"] for r in q("select tablename from pg_tables where schemaname='public'")]
        q("\n".join(f'ALTER TABLE public."{t}" ENABLE ROW LEVEL SECURITY;' for t in tables))
        print("schema loaded, RLS enabled on", len(tables), "tables")
    elif step == "data":
        sql = clean(gzip.decompress((ROOT / "db" / "data_dump.sql.gz").read_bytes()).decode())
        stm = statements(sql)
        batch, size, n = [], 0, 0
        for s in stm:
            batch.append(s)
            size += len(s)
            if size > 1_500_000:
                q("\n".join(batch)); n += len(batch); batch, size = [], 0
                print("loaded", n, "/", len(stm), flush=True)
        if batch:
            q("\n".join(batch)); n += len(batch)
        print("data statements:", n)
    elif step == "counts":
        tables = [r["tablename"] for r in q("select tablename from pg_tables where schemaname='public' order by 1")]
        res = q(" union all ".join(f"select '{t}' t, count(*) n from public.\"{t}\"" for t in tables))
        print(json.dumps({r["t"]: r["n"] for r in res}))


if __name__ == "__main__":
    main(sys.argv[1])
