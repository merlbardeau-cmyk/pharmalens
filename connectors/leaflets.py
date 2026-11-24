"""Phase 4: manufacturer / batch-release sites per product from the leaflet of that exact product.

ES: CIMA REST docSegmentado (PL section 6)      FR: BDPM product page (notice section "Fabricant")
EU: EMA product information PDF, Annex IIA (batch release + biological active substance manufacturer)
Every row carries the verbatim quote (evidence_quote). No section found -> gap, never a guess.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher  # noqa: E402
from enrich.leaflet_parser import START, html_to_lines, parse  # noqa: E402
from models.db import add_gap, connect, now  # noqa: E402

BIO_START = re.compile(r"^Name and address of the manufacturer\(?s?\)? of the biological active substance\(?s?\)?\s*:?$", re.I)


def write_sites(conn, product_id, sites, role, leaflet_url, source_url, source_name, raw_id):
    seen, uniq = set(), []
    for s in sites:  # same site listed under several dosage forms -> once per product
        k = (s["company"].lower(), s["address"].lower())
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    sites = uniq
    cur = conn.execute("SELECT row_id, evidence_quote, coalesce(site_country,'') FROM product_manufacturer WHERE product_id=%s"
                       " AND role=%s AND valid_to IS NULL", (product_id, role)).fetchall()
    if sorted((q, c) for _, q, c in cur) == sorted((s["quote"], s["country"] or "") for s in sites):
        return "same"
    for rid, _, _ in cur:
        conn.execute("UPDATE product_manufacturer SET valid_to=now() WHERE row_id=%s", (rid,))
    for s in sites:
        conn.execute(
            """INSERT INTO product_manufacturer (product_id, role, manufacturer_raw, site_address_raw, site_country,
                   country_basis, leaflet_url, evidence_quote, source_url, source_name, retrieved_at, status, raw_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'official',%s)""",
            (product_id, role, s["company"], s["address"], s["country"], s["country_basis"], leaflet_url, s["quote"],
             source_url, source_name, now(), raw_id))
    return "changed" if cur else "new"


def products(conn, where):
    return conn.execute(f"""SELECT DISTINCT p.product_id, p.authorisation_no, p.leaflet_url, p.name FROM product p
                            JOIN product_api pa USING (product_id) WHERE p.valid_to IS NULL AND {where}
                            ORDER BY p.product_id""").fetchall()


def run_es(limit=None):
    api = "https://cima.aemps.es/cima/rest/docSegmentado/contenido/2"
    st = dict(products=0, with_sites=0, sites=0, gaps=0, no_country=0)
    with connect() as conn:
        f = Fetcher(conn, "ES AEMPS CIMA REST", raw_dir="cima_leaflets")
        for pid, nreg, pl, name in products(conn, "p.source_name='ES AEMPS CIMA REST'")[:limit]:
            st["products"] += 1
            r, raw_id = f.get(api, params={"nregistro": nreg, "seccion": "6"})
            src = f"{api}?nregistro={nreg}&seccion=6"
            sites = []
            if r.status_code == 200 and r.content:
                try:
                    sites = parse(html_to_lines(" ".join(x.get("contenido", "") if isinstance(x, dict) else str(x) for x in r.json())), home_country="ES")
                except ValueError:
                    sites = []
            if not sites:
                st["gaps"] += 1
                add_gap(conn, "manufacturer", "product", pid, f"ES: Hersteller-Sektion im Prospekt nicht gefunden (HTTP {r.status_code})",
                        pl or src, "ES AEMPS CIMA REST")
                continue
            write_sites(conn, pid, sites, "batch_release", pl or src, src, "ES AEMPS CIMA REST", raw_id)
            st["with_sites"] += 1
            st["sites"] += len(sites)
            st["no_country"] += sum(1 for s in sites if not s["country"])
    print("ES leaflets", st, flush=True)
    return st


def run_fr(limit=None):
    st = dict(products=0, with_sites=0, sites=0, gaps=0, no_country=0)
    with connect() as conn:
        f = Fetcher(conn, "FR BDPM", raw_dir="bdpm_leaflets")
        for pid, cis, _, name in products(conn, "p.source_name='FR BDPM'")[:limit]:
            st["products"] += 1
            url = f"https://base-donnees-publique.medicaments.gouv.fr/medicament/{cis}/extrait"
            r, raw_id = f.get(url)
            lines = html_to_lines(r.text) if r.status_code == 200 else []
            # restrict to the notice part of the page (the SmPC part has no manufacturer section)
            idx = next((i for i, ln in enumerate(lines) if ln.lower().startswith("notice")), 0)
            sites = parse(lines[idx:], home_country="FR")
            if not sites:
                st["gaps"] += 1
                add_gap(conn, "manufacturer", "product", pid, f"FR: Rubrique 'Fabricant' nicht gefunden (HTTP {r.status_code})",
                        url, "FR BDPM")
                continue
            write_sites(conn, pid, sites, "batch_release", url + "#notice", url, "FR BDPM", raw_id)
            st["with_sites"] += 1
            st["sites"] += len(sites)
            st["no_country"] += sum(1 for s in sites if not s["country"])
    print("FR leaflets", st, flush=True)
    return st


def pdf_lines(content: bytes) -> list[str]:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
        t.write(content)
        t.flush()
        txt = subprocess.run(["pdftotext", "-enc", "UTF-8", t.name, "-"], capture_output=True, text=True).stdout
    out = []
    for ln in txt.splitlines():
        ln = re.sub(r"\s+", " ", ln).strip()
        if re.fullmatch(r"\d{1,3}", ln) or "no longer authorised" in ln.lower():
            continue  # page numbers / watermark
        out.append(ln if ln else "or")  # blank line separates address blocks in Annex IIA
    # collapse repeated separators
    return [ln for i, ln in enumerate(out) if not (ln == "or" and i and out[i - 1] == "or")]


def run_ema():
    st = dict(products=0, with_sites=0, sites=0, bio_sites=0, gaps=0)
    with connect() as conn:
        f = Fetcher(conn, "EMA Medicine data download", raw_dir="ema_product_information")
        for pid, emano, epar, name in products(conn, "p.natural_key LIKE 'EMA|%' AND p.product_status='Authorised'"):
            st["products"] += 1
            page, _ = f.get(epar)
            m = re.search(r'href="([^"]*product-information_en\.pdf)"', page.text)
            if not m:
                st["gaps"] += 1
                add_gap(conn, "manufacturer", "product", pid, "EMA: Product-Information-PDF auf EPAR-Seite nicht gefunden", epar,
                        "EMA Medicine data download")
                continue
            pdf_url = m.group(1) if m.group(1).startswith("http") else "https://www.ema.europa.eu" + m.group(1)
            r, raw_id = f.get(pdf_url)
            lines = pdf_lines(r.content)
            # Annex IIA batch release
            for i, ln in enumerate(lines):
                if START[2].match(ln):
                    lines_iia = lines[i:]
                    break
            else:
                lines_iia = []
            sites = [s for s in parse(lines_iia) if s["company"] != "or"] if lines_iia else []
            if sites:
                write_sites(conn, pid, sites, "batch_release", pdf_url, pdf_url, "EMA Medicine data download", raw_id)
                st["with_sites"] += 1
                st["sites"] += len(sites)
            else:
                st["gaps"] += 1
                add_gap(conn, "manufacturer", "product", pid, "EMA: Annex IIA nicht parsebar", pdf_url, "EMA Medicine data download")
            # Annex IIA biological active substance manufacturer = confirmed API manufacturer
            bi = next((i for i, ln in enumerate(lines) if BIO_START.match(ln)), None)
            if bi is not None:
                block = ["Name and address of the manufacturer(s) responsible for batch release"]  # reuse parser grammar
                for ln in lines[bi + 1:bi + 60]:
                    if START[2].match(ln):
                        break
                    block.append(ln)
                bio = [dict(s, quote=s["quote"].replace(block[0], lines[bi], 1)) for s in parse(block) if s["company"] != "or"]
                if bio:
                    write_sites(conn, pid, bio, "api_manufacturer", pdf_url, pdf_url, "EMA Medicine data download", raw_id)
                    st["bio_sites"] += len(bio)
    print("EMA Annex IIA", st, flush=True)
    return st


def annex_iia_sites(lines):
    for i, ln in enumerate(lines):
        if START[2].match(ln):
            return [s for s in parse(lines[i:]) if s["company"] != "or"]
    return []


def run_fr_central():
    """FR products authorised centrally: BDPM links to the EMA product information PDF -> Annex IIA of that PDF."""
    st = dict(products=0, with_sites=0, sites=0, still_gap=0)
    with connect() as conn:
        f = Fetcher(conn, "FR BDPM", raw_dir="bdpm_leaflets")
        fe = Fetcher(conn, "EMA Medicine data download", raw_dir="ema_product_information")
        rows = conn.execute("""SELECT g.gap_id, p.product_id, p.authorisation_no FROM gap g JOIN product p
                               ON p.product_id = g.entity_ref::bigint AND p.valid_to IS NULL
                               WHERE g.area='manufacturer' AND g.source_name='FR BDPM' AND g.resolved_at IS NULL""").fetchall()
        for gap_id, pid, cis in rows:
            st["products"] += 1
            url = f"https://base-donnees-publique.medicaments.gouv.fr/medicament/{cis}/extrait"
            r, _ = f.get(url)
            m = re.search(r'href="(https://www\.ema\.europa\.eu/[^"]+product-information_)fr\.pdf"', r.text)
            if not m:
                st["still_gap"] += 1
                continue
            pdf = (m.group(1) + "en.pdf").replace("/fr/documents/", "/en/documents/")
            pr, raw_id = fe.get(pdf)
            sites = annex_iia_sites(pdf_lines(pr.content)) if pr.status_code == 200 else []
            if not sites:
                st["still_gap"] += 1
                continue
            write_sites(conn, pid, sites, "batch_release", pdf, pdf, "EMA Medicine data download", raw_id)
            conn.execute("UPDATE gap SET resolved_at=now() WHERE gap_id=%s", (gap_id,))
            st["with_sites"] += 1
            st["sites"] += len(sites)
    print("FR central via EMA Annex IIA", st, flush=True)
    return st


if __name__ == "__main__":
    {"es": run_es, "fr": run_fr, "ema": run_ema, "fr_central": run_fr_central}[sys.argv[1]](*(int(a) for a in sys.argv[2:]))
