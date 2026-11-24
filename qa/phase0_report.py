"""Build the Phase 0 source report (Markdown) from the `source` table and resync `gap`."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import DSN, ROOT  # noqa: E402
from qa.sources_catalog import NOT_PROBED  # noqa: E402

ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
CAT = {"substance": "Wirkstoff-Stamm", "certificate": "API-Zertifikate & Werke", "approval_eu": "Zulassungen EU zentral",
       "national": "Nationale Register", "patent": "Patente & SPC", "shortage": "Engpässe", "tender": "Ausschreibungen",
       "volume": "Volumen & Handel", "company": "Firmenstruktur"}


def main() -> None:
    with psycopg.connect(DSN, autocommit=True) as conn:
        rows = conn.execute(
            """SELECT name, category, jurisdiction, probe_url, final_url, http_status, robots_status, access_method,
                      traffic_light, traffic_reason, licence_note, update_frequency
               FROM source ORDER BY array_position(ARRAY['substance','certificate','approval_eu','national','patent',
                      'shortage','tender','volume','company'], category), traffic_light, name""").fetchall()
        conn.execute("DELETE FROM gap WHERE area='source'")
        for r in rows:
            if r[8] == "red":
                conn.execute("INSERT INTO gap (area, entity_type, entity_ref, reason, where_obtainable, source_name)"
                             " VALUES ('source','source',%s,%s,%s,%s)", (r[0], r[9], r[3], r[0]))
        for name, jur, host, why in NOT_PROBED:
            conn.execute("INSERT INTO gap (area, entity_type, entity_ref, reason, where_obtainable, source_name)"
                         " VALUES ('source','source',%s,%s,%s,%s)", (name, why, host, name))
        n_gap = conn.execute("SELECT count(*) FROM gap WHERE area='source'").fetchone()[0]
        n_raw = conn.execute("SELECT count(*), coalesce(sum(bytes),0) FROM raw_object").fetchone()

    counts = {k: sum(1 for r in rows if r[8] == k) for k in ("green", "yellow", "red")}
    out = [f"# PharmaLens – Phase 0 Quellenbericht",
           f"Stand: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · geprüft: {len(rows)} Quellen · "
           f"🟢 {counts['green']} · 🟡 {counts['yellow']} · 🔴 {counts['red']} · nicht geprüft: {len(NOT_PROBED)}",
           f"Rohspeicher: {n_raw[0]} Objekte, {float(n_raw[1])/1e6:.1f} MB, SHA-256 in `raw_object`. Lücken in `gap`: {n_gap}.",
           "", "Ampel: 🟢 offizieller Download/API · 🟡 HTML erlaubt (Scraping nötig) · 🔴 nicht nutzbar (gesperrt, robots, WAF/CAPTCHA, Fehler).",
           "Lizenz-Hinweise mit [zu verifizieren] sind Kenntnisstand, noch nicht gegen die Nutzungsbedingungen der Quelle geprüft.", ""]
    for cat in CAT:
        sub = [r for r in rows if r[1] == cat]
        if not sub:
            continue
        out += [f"## {CAT[cat]}", "", "| | Quelle | Land | HTTP | robots | Zugriff | Befund | Lizenz | Rhythmus |",
                "|---|---|---|---|---|---|---|---|---|"]
        for r in sub:
            out.append(f"| {ICON[r[8]]} | [{r[0]}]({r[3]}) | {r[2]} | {r[5] or '–'} | {r[6]} | {r[7]} | "
                       f"{r[9].replace('|', '/')} | {r[10].replace('|', '/')} | {r[11]} |")
        out.append("")
    out += ["## Nicht geprüft (Host fehlt oder Quelle unbekannt)", "", "| Quelle | Land | Host | Grund |", "|---|---|---|---|"]
    out += [f"| {n} | {j} | {h} | {w} |" for n, j, h, w in NOT_PROBED]
    p = ROOT / "reports" / "phase0_report.md"
    p.write_text("\n".join(out) + "\n")
    print(p, counts, "gaps:", n_gap)


if __name__ == "__main__":
    main()
