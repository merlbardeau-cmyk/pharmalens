"""Shared HTTP + raw-storage helpers for all connectors.

Rules implemented here:
  * polite client: identifying User-Agent, per-host rate limit, robots.txt check
  * every downloaded body is stored under raw/<source>/<date>/<sha256>.<ext> and indexed in raw_object
"""
from __future__ import annotations

import hashlib
import mimetypes
import os
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
import psycopg

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"
DSN = os.environ.get("PHARMALENS_DSN", "postgresql://pharmalens:pharmalens@localhost/pharmalens")
USER_AGENT = "PharmaLensResearchBot/0.1 (+public-regulatory-data; polite crawler)"
MIN_INTERVAL_S = 1.5  # per host

_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def client() -> httpx.Client:
    verify = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
    if not Path(verify).exists():
        verify = True
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en,de;q=0.8,fr;q=0.6"},
        follow_redirects=True,
        timeout=httpx.Timeout(45.0, connect=20.0),
        verify=verify,
    )


def throttle(url: str) -> None:
    host = urlparse(url).netloc
    wait = MIN_INTERVAL_S - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()


def robots_status(c: httpx.Client, url: str) -> str:
    """allowed | disallowed | no_robots | unreachable"""
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        try:
            throttle(base)
            r = c.get(base + "/robots.txt")
            if r.status_code >= 400 or "text/html" in r.headers.get("content-type", ""):
                _robots[base] = None
            else:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(r.text.splitlines())
                _robots[base] = rp
        except httpx.HTTPError:
            _robots[base] = False  # type: ignore[assignment]
    rp = _robots[base]
    if rp is False:
        return "unreachable"
    if rp is None:
        return "no_robots"
    return "allowed" if rp.can_fetch(USER_AGENT, url) else "disallowed"


def store_raw(source: str, url: str, body: bytes, content_type: str | None, http_status: int,
              conn: psycopg.Connection | None = None, source_id: int | None = None) -> tuple[str, str]:
    sha = hashlib.sha256(body).hexdigest()
    ext = mimetypes.guess_extension((content_type or "").split(";")[0].strip()) or ".bin"
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    d = RAW_DIR / source / day
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{sha}{ext}"
    if not path.exists():
        path.write_bytes(body)
    rel = str(path.relative_to(ROOT))
    if conn is not None:
        conn.execute(
            """INSERT INTO raw_object (source_id, url, sha256, path, content_type, bytes, http_status)
               VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (url, sha256) DO NOTHING""",
            (source_id, url, sha, rel, content_type, len(body), http_status),
        )
    return sha, rel
