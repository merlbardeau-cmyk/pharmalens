"""Upload the raw store (raw/**) to a PRIVATE Supabase Storage bucket 'raw' (same relative paths as raw_object.path).

Auth: the project secret key is injected by the network proxy as `apikey` header (never in code).
Files > 45 MB are split into .partN objects plus a .parts.json manifest (sha256 of the whole file is the filename).
Idempotent: objects that already exist with the same size are skipped.
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

REF = "kulodmfvlxocvpkyyoiw"
BASE = f"https://{REF}.supabase.co/storage/v1"
BUCKET = "raw"
ROOT = Path(__file__).resolve().parents[1]
PART = 45 * 1024 * 1024
CT = {".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".pdf": "application/pdf",
      ".json": "application/json", ".zip": "application/zip", ".csv": "text/csv", ".txt": "text/plain",
      ".html": "text/html", ".xml": "application/xml", ".js": "application/javascript"}


def client():
    return httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0), verify="/root/.ccr/ca-bundle.crt",
                        headers={"apikey": "proxy-injected"})


def ensure_bucket(c):
    r = c.get(f"{BASE}/bucket/{BUCKET}")
    if r.status_code == 200:
        return r.json()
    r = c.post(f"{BASE}/bucket", json={"id": BUCKET, "name": BUCKET, "public": False})
    r.raise_for_status()
    return r.json()


def existing(c, prefix=""):
    """map path -> size for objects already in the bucket (recursive listing)."""
    out, stack = {}, [prefix]
    while stack:
        p = stack.pop()
        offset = 0
        while True:
            r = c.post(f"{BASE}/object/list/{BUCKET}", json={"prefix": p, "limit": 1000, "offset": offset})
            r.raise_for_status()
            items = r.json()
            for it in items:
                full = f"{p}/{it['name']}".lstrip("/")
                if it.get("id") is None:          # folder
                    stack.append(full)
                else:
                    out[full] = (it.get("metadata") or {}).get("size")
            if len(items) < 1000:
                break
            offset += 1000
    return out


def put(c, key, data: bytes, ctype: str):
    for a in range(4):
        r = c.post(f"{BASE}/object/{BUCKET}/{key}", content=data, headers={"Content-Type": ctype, "x-upsert": "true"})
        if r.status_code in (200, 201):
            return True
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(5 * (a + 1))
            continue
        raise RuntimeError(f"{key}: HTTP {r.status_code} {r.text[:200]}")
    return False


def upload_one(path: Path, have: dict):
    rel = str(path.relative_to(ROOT))
    data = path.read_bytes()
    ctype = CT.get(path.suffix.lower(), "application/octet-stream")
    c = client()
    if len(data) <= PART:
        if have.get(rel) == len(data):
            return rel, "skip", len(data)
        put(c, rel, data, ctype)
        return rel, "up", len(data)
    parts = [data[i:i + PART] for i in range(0, len(data), PART)]
    manifest = {"file": rel, "bytes": len(data), "parts": [f"{rel}.part{i + 1}" for i in range(len(parts))],
                "reassemble": "cat part1 part2 ... > file; sha256 must equal the file name"}
    for k, chunk in zip(manifest["parts"], parts):
        if have.get(k) != len(chunk):
            put(c, k, chunk, "application/octet-stream")
    put(c, f"{rel}.parts.json", json.dumps(manifest).encode(), "application/json")
    return rel, f"split:{len(parts)}", len(data)


def main(step="upload"):
    c = client()
    if step == "upload":
        print("bucket", ensure_bucket(c).get("public"), "(public flag)")
        have = existing(c, "raw")
        files = sorted(p for p in (ROOT / "raw").rglob("*") if p.is_file())
        st = {"up": 0, "skip": 0, "split": 0, "bytes": 0}
        with ThreadPoolExecutor(max_workers=6) as ex:
            for i, (rel, res, n) in enumerate(ex.map(lambda p: upload_one(p, have), files), 1):
                st["split" if res.startswith("split") else res] += 1
                st["bytes"] += n
                if i % 250 == 0:
                    print(i, "/", len(files), st, flush=True)
        print("done", st)
    elif step == "verify":
        have = existing(c, "raw")
        files = sorted(p for p in (ROOT / "raw").rglob("*") if p.is_file())
        missing, wrong = [], []
        for p in files:
            rel, n = str(p.relative_to(ROOT)), p.stat().st_size
            if n > PART:
                parts = [k for k in have if k.startswith(rel + ".part") and not k.endswith(".json")]
                if sum(have[k] or 0 for k in parts) != n:
                    wrong.append(rel)
            elif rel not in have:
                missing.append(rel)
            elif have[rel] != n:
                wrong.append(rel)
        print(json.dumps({"local_files": len(files), "storage_objects": len(have), "missing": len(missing),
                          "size_mismatch": len(wrong), "examples": (missing + wrong)[:5]}))


if __name__ == "__main__":
    main(*sys.argv[1:])
