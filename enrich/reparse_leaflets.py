"""Re-run the leaflet parser on stored raw objects (no network). Parser fixes create new versions, old ones stay."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import ROOT  # noqa: E402
from connectors.leaflets import annex_iia_sites, pdf_lines, write_sites  # noqa: E402
from enrich.leaflet_parser import html_to_lines, parse  # noqa: E402
from models.db import add_gap, connect  # noqa: E402


def lines_for(source_name, raw_bytes):
    if source_name == "ES AEMPS CIMA REST":
        import json
        j = json.loads(raw_bytes.decode("utf-8"))
        return html_to_lines(" ".join(x.get("contenido", "") if isinstance(x, dict) else str(x) for x in j)), "ES", "html"
    if source_name == "FR BDPM":
        ls = html_to_lines(raw_bytes.decode("utf-8", errors="ignore"))
        idx = next((i for i, ln in enumerate(ls) if ln.lower().startswith("notice")), 0)
        return ls[idx:], "FR", "html"
    home = {"NL CBG Geneesmiddeleninformatiebank": "NL", "AT BASG Arzneispezialitätenregister": "AT", "DK DKMA": "DK"}.get(source_name)
    if home:
        return pdf_lines(raw_bytes), home, "pdf_leaflet"
    return pdf_lines(raw_bytes), None, "pdf"


def run():
    st = dict(products=0, changed=0, same=0, now_gap=0)
    with connect() as conn:
        groups = conn.execute("""SELECT pm.product_id, pm.role, pm.source_name, pm.source_url, pm.leaflet_url, max(pm.raw_id)
                                 FROM product_manufacturer pm WHERE pm.valid_to IS NULL
                                 GROUP BY 1,2,3,4,5""").fetchall()
        for pid, role, src, url, leaflet, raw_id in groups:
            path = conn.execute("SELECT path FROM raw_object WHERE raw_id=%s", (raw_id,)).fetchone()[0]
            data = (ROOT / path).read_bytes()
            lines, home, kind = lines_for(src, data)
            if role == "api_manufacturer":
                continue  # Annex IIA biological section: unchanged grammar
            sites = annex_iia_sites(lines) if kind == "pdf" else parse(lines, home_country=home)
            st["products"] += 1
            if not sites:
                conn.execute("UPDATE product_manufacturer SET valid_to=now() WHERE product_id=%s AND role=%s AND valid_to IS NULL",
                             (pid, role))
                add_gap(conn, "manufacturer", "product", pid, "Hersteller-Sektion nach Parser-Korrektur ohne gültigen Standort",
                        leaflet, src)
                st["now_gap"] += 1
                continue
            res = write_sites(conn, pid, sites, role, leaflet, url, src, raw_id)
            st[res if res in st else "changed"] += 1
    print("reparse", st)


if __name__ == "__main__" and len(sys.argv) == 1:
    run()


def reparse_gaps():
    """Re-evaluate open manufacturer gaps from stored raw objects (no network); classify scans without text."""
    st = dict(gaps=0, resolved=0, scans=0, still_gap=0)
    with connect() as conn:
        rows = conn.execute("""SELECT gap_id, entity_ref, where_obtainable, source_name FROM gap WHERE area='manufacturer'
                               AND resolved_at IS NULL AND reason NOT LIKE '%%Parallelimport%%'
                               AND source_name IN ('ES AEMPS CIMA REST','FR BDPM','NL CBG Geneesmiddeleninformatiebank',
                                                   'AT BASG Arzneispezialitätenregister','DK DKMA')""").fetchall()
        for gap_id, pid, url, src in rows:
            st["gaps"] += 1
            raw = conn.execute("SELECT raw_id, path FROM raw_object WHERE url=%s ORDER BY raw_id DESC LIMIT 1", (url,)).fetchone()
            if not raw:
                st["still_gap"] += 1
                continue
            data = (ROOT / raw[1]).read_bytes()
            lines, home, kind = lines_for(src, data)
            sites = annex_iia_sites(lines) if kind == "pdf" else parse(lines, home_country=home)
            if sites:
                write_sites(conn, int(pid), sites, "batch_release", url, url, src, raw[0])
                conn.execute("UPDATE gap SET resolved_at=now() WHERE gap_id=%s", (gap_id,))
                st["resolved"] += 1
            elif kind.startswith("pdf") and len(lines) < 25:
                conn.execute("UPDATE gap SET reason=%s WHERE gap_id=%s",
                             ("PDF ist ein Scan ohne Textebene – Hersteller nur per OCR lesbar (nicht automatisiert)", gap_id))
                st["scans"] += 1
            else:
                st["still_gap"] += 1
    print("reparse gaps", st)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "gaps":
    reparse_gaps()
