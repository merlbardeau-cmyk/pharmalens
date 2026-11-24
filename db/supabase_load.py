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
    """split pg_dump output into statements; a ';' only ends a statement outside single-quoted strings and $$ blocks"""
    out, cur, in_quote, in_dollar = [], [], False, False
    for line in sql.splitlines():
        if not cur and not in_quote and line.startswith("--"):
            continue
        cur.append(line)
        if not in_dollar and line.count("'") % 2 == 1:   # '' escapes keep parity, odd count toggles
            in_quote = not in_quote
        if not in_quote and line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        if not in_quote and not in_dollar and line.rstrip().endswith(";"):
            stmt = "\n".join(cur).strip()
            if stmt:
                out.append(stmt)
            cur = []
    if cur and "\n".join(cur).strip():
        raise ValueError("unterminated statement at end of dump")
    return out


def main(step: str):
    if step == "reset":
        tables = [r["tablename"] for r in q("select tablename from pg_tables where schemaname='public'")]
        if tables:
            q("\n".join(f'DROP TABLE IF EXISTS public."{t}" CASCADE;' for t in tables))
        q("DROP SEQUENCE IF EXISTS public.entity_seq CASCADE; DROP TYPE IF EXISTS public.data_status CASCADE; "
          "DROP TYPE IF EXISTS public.link_confidence CASCADE;")
        print("dropped", len(tables), "tables")
    elif step == "check":
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
    elif step == "data_json":
        import secrets
        import psycopg
        local = psycopg.connect("postgresql://pharmalens:pharmalens@localhost/pharmalens")
        tables = [r[0] for r in local.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")]
        first = ["source", "raw_object"]  # FK targets first
        tables = first + [t for t in tables if t not in first]
        for t in tables:
            n = local.execute(f'SELECT count(*) FROM public."{t}"').fetchone()[0]
            done = 0
            while done < n:
                rows = local.execute(f'SELECT coalesce(json_agg(x), \'[]\') FROM (SELECT * FROM public."{t}" ORDER BY 1 '
                                     f'LIMIT 1500 OFFSET {done}) x').fetchone()[0]
                payload = json.dumps(rows, ensure_ascii=False)
                tag = "pl" + secrets.token_hex(6)
                assert f"${tag}$" not in payload
                q(f'INSERT INTO public."{t}" SELECT * FROM json_populate_recordset(null::public."{t}", ${tag}${payload}${tag}$::json);')
                done += len(rows)
            print(t, done, flush=True)
        seq = local.execute("SELECT last_value FROM entity_seq").fetchone()[0]
        q(f"SELECT setval('public.entity_seq', {seq});")
        for t, col in local.execute("""SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='public'
                                        AND column_default LIKE 'nextval(%%' AND column_default NOT LIKE '%%entity_seq%%'""").fetchall():
            mx = local.execute(f'SELECT coalesce(max("{col}"),0) FROM public."{t}"').fetchone()[0]
            if mx:
                q(f"SELECT setval(pg_get_serial_sequence('public.\"{t}\"', '{col}'), {mx});")
        print("sequences set")
    elif step == "counts":
        tables = [r["tablename"] for r in q("select tablename from pg_tables where schemaname='public' order by 1")]
        res = q(" union all ".join(f"select '{t}' t, count(*) n from public.\"{t}\"" for t in tables))
        print(json.dumps({r["t"]: r["n"] for r in res}))


if __name__ == "__main__":
    main(sys.argv[1])
