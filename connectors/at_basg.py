"""AT BASG (Medikamente Info Austria): products from browser-collected search results + manufacturers from the
Gebrauchsinformation PDF. Usage terms (basg.gv.at/…/nutzungshinweise): reuse allowed, content must not be altered
-> verbatim quotes only. Covers human AND veterinary products.

Input: JSON written by connectors/js/basg_collect.js (rendered public site, responses the page itself receives).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher, source_id, store_raw  # noqa: E402
from connectors.leaflets import pdf_lines, write_sites  # noqa: E402
from enrich.leaflet_parser import parse  # noqa: E402
from models.countries import country_of  # noqa: E402
from models.db import SubstanceMatcher, add_gap, connect  # noqa: E402
from models.product_writer import ProductWriter  # noqa: E402

SRC = "AT BASG Arzneispezialitätenregister"
SITE = "https://medikamente.basg.gv.at/de/medicinal-products/"
VET_HINT = ("für tiere", "für schweine", "für rinder", "für hunde", "für katzen", "für pferde", "für schafe", "für hühner",
            "für puten", "für kälber", "ad us. vet", "tierarzneimittel")


def run(items_file: str, limit=None):
    st = dict(products=0, leaflets=0, with_sites=0, sites=0, gaps=0, no_leaflet=0, central=0)
    data = json.loads(Path(items_file).read_text())
    with connect() as conn:
        f = Fetcher(conn, SRC, raw_dir="basg")
        _, _ = store_raw("basg", SITE + "#search", Path(items_file).read_bytes(), "application/json", 200, conn, source_id(conn, SRC))
        raw_id = conn.execute("SELECT max(raw_id) FROM raw_object WHERE url=%s", (SITE + "#search",)).fetchone()[0]
        m, w = SubstanceMatcher(conn), ProductWriter(conn, SRC)
        seen, todo = set(), []
        for block in data:
            for it in block["items"]:
                if it["id"] in seen:
                    continue
                seen.add(it["id"])
                subst = "; ".join(it.get("substances") or [])
                ids = m.match(subst)
                if not ids:
                    continue
                auth = it["authNumber"]
                central = auth.upper().startswith("EU/")
                vet = any(h in it["name"].lower() for h in VET_HINT)
                pl = it.get("packageLeaflet")
                url = f"https://medikamente.basg.gv.at/documents/{auth}__{pl['type']}.pdf" if pl and not central else None
                pid = w.write(f"AT|{auth}|{it['name'].strip().lower()}", dict(
                    name=it["name"], country="AT", mah_raw=(it.get("approvalHolder") or "").split(",")[0].strip() or None,
                    authorisation_no=auth, procedure="centralised" if central else ("DCP/MRP" if it.get("mrpDcpNumber") else "national"),
                    procedure_no=it.get("mrpDcpNumber"), product_status="Lieferengpass gemeldet" if it.get("drugShortage") else None,
                    is_veterinary=vet, leaflet_url=url), ids, subst, SITE + f"?q={auth}", raw_id)
                st["products"] += 1
                if central:
                    st["central"] += 1  # leaflet = EMA product information (Annex IIA via EMA connector)
                elif not url:
                    st["no_leaflet"] += 1
                    add_gap(conn, "manufacturer", "product", pid, "AT: keine Gebrauchsinformation im Register", SITE, SRC)
                else:
                    todo.append((pid, url))
        for pid, url in todo[:limit]:
            pr, praw = f.get(url)
            st["leaflets"] += 1
            sites = parse(pdf_lines(pr.content), home_country="AT") if pr.status_code == 200 and pr.content[:4] == b"%PDF" else []
            if not sites:
                st["gaps"] += 1
                add_gap(conn, "manufacturer", "product", pid, f"AT: Hersteller-Abschnitt in Gebrauchsinformation nicht gefunden (HTTP {pr.status_code})", url, SRC)
                continue
            write_sites(conn, pid, sites, "batch_release", url, url, SRC, praw)
            st["with_sites"] += 1
            st["sites"] += len(sites)
        print("AT BASG", st, "products written:", w.stats, flush=True)
        return st


if __name__ == "__main__":
    run(sys.argv[1], *(int(a) for a in sys.argv[2:]))
