"""DK DKMA indlaegsseddel.dk: products + manufacturers ('Fremstiller') from the official patient leaflet PDF.

Input: JSON from connectors/js/dkma_collect.js (search by INN and by Danish brand names taken from EMA Art.57).
API mapping: name matcher; for brand-only names the API comes from the Art.57 DK product with that brand (derived link
would be weaker, so such rows keep status official only for the leaflet facts, the substance link is logged).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher, source_id, store_raw  # noqa: E402
from connectors.leaflets import pdf_lines, write_sites  # noqa: E402
from enrich.leaflet_parser import parse  # noqa: E402
from models.db import SubstanceMatcher, add_gap, connect, norm_text  # noqa: E402
from models.product_writer import ProductWriter  # noqa: E402

SRC = "DK DKMA"
SITE = "https://xnet.dkma.dk/indlaegsseddel/leaflets/leaflets.faces"


def brand_map(conn):
    out = {}
    for name, aid in conn.execute("""SELECT p.name, pa.api_id FROM product p JOIN product_api pa USING (product_id)
                                     WHERE p.valid_to IS NULL AND p.country='DK'""").fetchall():
        b = norm_text(re.sub(r'["®™]', "", name)).split(" ")[0]
        out.setdefault(b, set()).add(aid)
    return out


def run(items_file: str, limit=None):
    st = dict(rows=0, products=0, unmatched=0, leaflets=0, with_sites=0, sites=0, gaps=0, no_pdf=0)
    data = json.loads(Path(items_file).read_text())
    with connect() as conn:
        f = Fetcher(conn, SRC, raw_dir="dkma")
        store_raw("dkma", SITE + "#search", Path(items_file).read_bytes(), "application/json", 200, conn, source_id(conn, SRC))
        raw_id = conn.execute("SELECT max(raw_id) FROM raw_object WHERE url=%s", (SITE + "#search",)).fetchone()[0]
        m, w, brands = SubstanceMatcher(conn), ProductWriter(conn, SRC), brand_map(conn)
        seen, todo = set(), []
        for block in data:
            for row in block["rows"]:
                st["rows"] += 1
                key = f"DK|{row['mt']}|{row['name']}|{row['strength']}"
                if key in seen:
                    continue
                seen.add(key)
                ids = m.match(row["name"]) or sorted(brands.get(norm_text(re.sub(r'["®™]', "", row["name"])).split(" ")[0], []))
                if not ids:
                    st["unmatched"] += 1
                    continue
                pid = w.write(key, dict(name=row["name"], country="DK", mah_raw=row["company"], authorisation_no=f"MT {row['mt']}",
                                        strength=row["strength"], form=row["form"], product_status=row["status"], is_veterinary=False,
                                        leaflet_url=row["pdf"]), ids, row["name"], SITE + f"#mt={row['mt']}", raw_id)
                st["products"] += 1
                if row["pdf"]:
                    todo.append((pid, row["pdf"]))
                else:
                    st["no_pdf"] += 1
                    add_gap(conn, "manufacturer", "product", pid, "DK: keine Indlægsseddel verlinkt", SITE, SRC)
        for pid, url in todo[:limit]:
            pr, praw = f.get(url)
            st["leaflets"] += 1
            sites = parse(pdf_lines(pr.content), home_country="DK") if pr.status_code == 200 and pr.content[:4] == b"%PDF" else []
            if not sites:
                st["gaps"] += 1
                add_gap(conn, "manufacturer", "product", pid, f"DK: Fremstiller-Abschnitt nicht gefunden (HTTP {pr.status_code})", url, SRC)
                continue
            write_sites(conn, pid, sites, "batch_release", url, url, SRC, praw)
            st["with_sites"] += 1
            st["sites"] += len(sites)
        print("DK DKMA", st, "products written:", w.stats, flush=True)
        return st


if __name__ == "__main__":
    run(sys.argv[1], *(int(a) for a in sys.argv[2:]))
