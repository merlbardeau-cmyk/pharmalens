"""Phase 0: probe every source, classify (green/yellow/red), write to `source` + raw store + JSON report."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import DSN, ROOT, client, robots_status, store_raw, throttle  # noqa: E402
from qa.sources_catalog import NOT_PROBED, SOURCES  # noqa: E402

CAPTCHA_RX = re.compile(r"captcha|cf-challenge|Just a moment\.\.\.|hcaptcha|recaptcha|challenge-platform", re.I)
LOGIN_RX = re.compile(r'type=["\']password["\']', re.I)
FILE_LINK_RX = re.compile(r'href=["\'][^"\']*?(?:\.(xlsx?|zip|csv|txt|xml|json|gz)|/media/\d+/(download))(\?[^"\']*)?["\']', re.I)
WAF_RX = re.compile(r"Web Page Blocked|Request Rejected|Attack ID", re.I)


def classify(s: dict, r: httpx.Response | None, err: str | None, robots: str) -> tuple[str, str, str]:
    """returns (traffic_light, access_method, reason)"""
    if r is None:
        return "red", "none", f"nicht erreichbar: {err}"
    if s.get("tos_block"):
        return "red", "none", f"HTTP {r.status_code}, technisch erreichbar, aber: {s['tos_block']}"
    ct = r.headers.get("content-type", "").lower()
    body = r.text[:200_000] if ("text" in ct or "json" in ct or "xml" in ct) else ""
    if WAF_RX.search(body):
        return "red", "none", f"HTTP {r.status_code}, Web Application Firewall blockiert Cloud-IP/Bot – wird nicht umgangen"
    if CAPTCHA_RX.search(body) and (r.status_code in (403, 429, 503) or len(body) < 30_000):
        return "red", "none", f"HTTP {r.status_code}, CAPTCHA/Bot-Challenge erkannt – wird nicht umgangen"
    if robots == "disallowed":
        return "red", "none", f"HTTP {r.status_code}, robots.txt verbietet den Pfad"
    if r.status_code in (401, 403):
        if s["expected"] == "api":
            return "green", "api", f"HTTP {r.status_code}: API erreichbar, Zugang erfordert (kostenlosen) Key/Registrierung"
        return "red", "none", f"HTTP {r.status_code}: Zugriff verweigert"
    if r.status_code == 405 and s["expected"] == "api":
        return "green", "api", "API erreichbar (Methode prüfen)"
    if r.status_code >= 400:
        return "red", "none", f"HTTP {r.status_code}"
    if LOGIN_RX.search(body) and s["expected"] != "api":
        return "red", "none", "Login-Formular – wird nicht verwendet"
    if s["expected"] == "api":
        if "json" in ct or "xml" in ct:
            return "green", "api", f"API liefert {ct.split(';')[0]}"
        return "yellow", "html", f"API-Endpunkt liefert {ct.split(';')[0]} statt JSON/XML"
    if s["expected"] == "download":
        if "html" not in ct:
            return "green", "download", f"Direkter Download ({ct.split(';')[0]}, {len(r.content):,} Bytes)"
        links = FILE_LINK_RX.findall(body)
        if links:
            return "green", "download", f"Download-Seite mit {len(links)} Datei-Links ({', '.join(sorted({(l[0] or l[1]).lower() for l in links}))})"
        return "yellow", "html", "Download erwartet, aber keine Datei-Links im HTML gefunden (evtl. JS)"
    # html
    js_only = len(re.sub(r"<script.*?</script>", "", body, flags=re.S)) < 3000
    return "yellow", "html", "HTML zugänglich" + (" – Seite JS-gerendert, Playwright nötig" if js_only else "")


def main() -> None:
    now = datetime.now(timezone.utc)
    results = []
    with psycopg.connect(DSN, autocommit=True) as conn, client() as c:
        only = set(sys.argv[1:])
        for s in SOURCES:
            if only and s["name"] not in only:
                continue
            url = s["probe"]
            r, err = None, None
            robots = robots_status(c, url)
            try:
                throttle(url)
                if s.get("method") == "POST":
                    r = c.post(url, json=s["body"])
                else:
                    r = c.get(url)
            except httpx.HTTPError as e:
                err = f"{type(e).__name__}: {e}"[:200]
            light, access, reason = classify(s, r, err, robots)
            sid = conn.execute(
                """INSERT INTO source (name, category, jurisdiction, base_url, probe_url, access_method, http_status,
                       final_url, robots_status, licence_note, update_frequency, traffic_light, traffic_reason,
                       last_checked, last_success)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (name) DO UPDATE SET probe_url=EXCLUDED.probe_url, access_method=EXCLUDED.access_method,
                       http_status=EXCLUDED.http_status, final_url=EXCLUDED.final_url, robots_status=EXCLUDED.robots_status,
                       licence_note=EXCLUDED.licence_note, update_frequency=EXCLUDED.update_frequency,
                       traffic_light=EXCLUDED.traffic_light, traffic_reason=EXCLUDED.traffic_reason,
                       last_checked=EXCLUDED.last_checked,
                       last_success=COALESCE(EXCLUDED.last_success, source.last_success)
                   RETURNING source_id""",
                (s["name"], s["category"], s["jur"], s["base"], url, access, r.status_code if r else None,
                 str(r.url) if r else None, robots, s["licence"], s["freq"], light, reason, now,
                 now if light != "red" else None),
            ).fetchone()[0]
            sha = None
            if r is not None:
                sha, _ = store_raw("phase0_" + re.sub(r"\W+", "_", s["name"]).strip("_").lower(), url, r.content,
                                   r.headers.get("content-type"), r.status_code, conn, sid)
            if light == "red":
                conn.execute("INSERT INTO gap (area, entity_type, entity_ref, reason, where_obtainable, source_name)"
                             " VALUES ('source','source',%s,%s,%s,%s)",
                             (s["name"], reason, s["base"], s["name"]))
            results.append(dict(name=s["name"], category=s["category"], jur=s["jur"], probe=url,
                                status=r.status_code if r else None, final_url=str(r.url) if r else None,
                                content_type=r.headers.get("content-type") if r else None,
                                bytes=len(r.content) if r else 0, robots=robots, light=light, access=access,
                                reason=reason, licence=s["licence"], freq=s["freq"], sha256=sha))
            print(f"{light:6} {s['name']:40} {r.status_code if r else '---'} {robots:11} {reason}", flush=True)
        for name, jur, host, why in ([] if only else NOT_PROBED):
            conn.execute("INSERT INTO gap (area, entity_type, entity_ref, reason, where_obtainable, source_name)"
                         " VALUES ('source','source',%s,%s,%s,%s)", (name, why, host, name))
    out = ROOT / "reports" / ("phase0_sources.json" if not only else "phase0_recheck.json")
    out.write_text(json.dumps(dict(checked_at=now.isoformat(), results=results,
                                   not_probed=[dict(name=n, jur=j, host=h, reason=w) for n, j, h, w in NOT_PROBED]),
                              indent=2, ensure_ascii=False))
    print("->", out)


if __name__ == "__main__":
    main()
