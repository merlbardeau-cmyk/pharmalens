"""Market data per country (Market 360).

FR  BDPM CIS_CIP (packs, price, reimbursement rate), CIS_GENER (generic groups), Open Medic (reimbursed packs and
    amounts per CIP13 and year, Assurance Maladie, Licence Ouverte), ANSM shortages list.
ES  Nomenclátor de facturación (Ministerio de Sanidad): price per pack (PVP).
DK  Medstat (Sundhedsdatastyrelsen): annual sales per ATC.

Every row keeps source_url, source_name, retrieved_at, status and the raw file id. No value is estimated.

    python connectors/market.py fr | es | dk
"""
from __future__ import annotations

import csv
import gzip
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher  # noqa: E402
from models.db import SubstanceMatcher, add_gap, connect, now  # noqa: E402

SOURCES = [  # name, category, jurisdiction, base_url, probe_url, access, licence, frequency
    ("FR Open Medic", "volume", "FR", "https://open-data-assurance-maladie.ameli.fr/medicaments/",
     "https://www.data.gouv.fr/api/1/datasets/open-medic-base-complete-sur-les-depenses-de-medicaments-interregimes/",
     "download", "Licence Ouverte / Etalab (fr-lo)", "yearly"),
    ("ES Nomenclator", "price", "ES", "https://www.sanidad.gob.es/profesionales/nomenclator.do",
     "https://www.sanidad.gob.es/profesionales/nomenclator.do?metodo=nomenclatorExcel", "download",
     "Ministerio de Sanidad, public billing nomenclature [to be verified]", "monthly"),
    ("DK Medicinpriser", "price", "DK", "https://sundhedsdatabank.dk/medicin/medicinpriser-menu/medicinpriser",
     "https://sundhedsdatabank.dk/medicin/medicinpriser-menu/medicinpriser", "download", "Sundhedsdatastyrelsen, public price statistics [to be verified]", "biweekly"),
    ("DK Medstat", "volume", "DK", "https://sundhedsdatabank.dk/medicin/", "https://sundhedsdatabank.dk/medicin/aarlige-opgoerelser-medstat",
     "download", "Sundhedsdatastyrelsen, public statistics [to be verified]", "yearly"),
]
GEN_TYPE = {"0": "reference", "1": "generic", "2": "complementary", "4": "substitutable"}
UNIT_RX = re.compile(r"(\d+(?:[.,]\d+)?)\s*(comprim|gélule|gelule|capsule|sachet|ampoule|flacon|seringue|stylo|cartouche|suppositoire|"
                     r"patch|dispositif|récipient|recipient|dose|pastille|lyophilisat|ovule)", re.I)


def register(conn):
    for name, cat, jur, base, probe, acc, lic, freq in SOURCES:
        conn.execute("""INSERT INTO source (name, category, jurisdiction, base_url, probe_url, access_method, licence_note,
                        update_frequency, traffic_light, traffic_reason, last_checked)
                        SELECT %s,%s,%s,%s,%s,%s,%s,%s,'green','Official download; robots.txt allows the path',now()
                        WHERE NOT EXISTS (SELECT 1 FROM source WHERE name=%s)""",
                     (name, cat, jur, base, probe, acc, lic, freq, name))


def units(text: str) -> int | None:
    """units per pack from a BDPM pack description, e.g. 'boîte de 3 plaquette(s) ... de 10 comprimé(s)' -> 30"""
    m = UNIT_RX.search(text or "")
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    pre = re.search(r"(\d+)\s*(?:plaquette|blister|sachet|étui|tube)\(?s?\)?[^\d]{0,60}de\s*$", (text or "")[:m.start()], re.I)
    if pre:
        n *= int(pre.group(1))
    return int(n) if n == int(n) and n > 0 else None


def num(s: str):
    s = (s or "").strip().replace(".", "").replace(",", ".") if re.search(r",\d{1,2}$", (s or "").strip()) else (s or "").strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def close(conn, table, where, args):
    conn.execute(f"UPDATE {table} SET valid_to=now() WHERE valid_to IS NULL AND {where}", args)


def fr():
    B = "https://base-donnees-publique.medicaments.gouv.fr/download/file/"
    st = defaultdict(int)
    with connect() as conn:
        register(conn)
        f = Fetcher(conn, "FR BDPM")
        prod = dict(conn.execute("SELECT authorisation_no, product_id FROM product WHERE valid_to IS NULL AND natural_key LIKE 'FR|CIS|%%'").fetchall())
        # 1) packs, prices, reimbursement
        r, raw = f.get(B + "CIS_CIP_bdpm.txt")
        txt = r.content.decode("utf-8", errors="strict") if r.content[:3] != b"\xef\xbb\xbf" else r.content.decode("utf-8-sig")
        close(conn, "price", "country='FR' AND source_name='FR BDPM'", ())
        cip_to_pid, rows = {}, []
        for row in csv.reader(io.StringIO(txt), delimiter="\t"):
            if len(row) < 10:
                continue
            pid = prod.get(row[0].strip())
            cip13 = row[6].strip()
            if pid:
                cip_to_pid[cip13] = pid
            price = num(row[9]) if len(row) > 9 else None
            if not pid or price is None:
                continue
            u = units(row[2])
            rows.append(("fdf_list", pid, "FR", row[2].strip()[:300], price, "EUR", "public price excl. dispensing fee (prix sans honoraire)",
                         u, "unit" if u else None, round(price / u, 4) if u else None, row[5] or None, cip13, (row[8] or "").strip() or None,
                         B + "CIS_CIP_bdpm.txt", "FR BDPM", now(), raw))
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO price (level, product_id, country, pack_text, value, currency, price_type, units_per_pack, unit,
                               normalized_value, price_date, pack_code, reimbursement_rate, source_url, source_name, retrieved_at, status, raw_id)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,to_date(%s,'DD/MM/YYYY'),%s,%s,%s,%s,%s,'official',%s)""", rows)
        st["prices"] = len(rows)
        # 2) generic groups
        r, raw = f.get(B + "CIS_GENER_bdpm.txt")
        try:
            txt = r.content.decode("utf-8")
        except UnicodeDecodeError:
            txt = r.content.decode("latin-1")
        close(conn, "product_generic", "source_name='FR BDPM'", ())
        rows = []
        for row in csv.reader(io.StringIO(txt), delimiter="\t"):
            if len(row) >= 4 and prod.get(row[2].strip()) and row[3].strip() in GEN_TYPE:
                rows.append((prod[row[2].strip()], row[0].strip(), row[1].strip()[:300], GEN_TYPE[row[3].strip()], B + "CIS_GENER_bdpm.txt", "FR BDPM", now(), raw))
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO product_generic (product_id, group_id, group_label, generic_type, source_url, source_name,
                               retrieved_at, raw_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""", rows)
        st["generic_links"] = len(rows)
        # 3) Open Medic volumes per CIP13 (latest year available)
        om = Fetcher(conn, "FR Open Medic", raw_dir="open_medic")
        year = None
        for y in (2025, 2024):
            page, _ = om.get(f"https://open-data-assurance-maladie.ameli.fr/medicaments/download2.php?Dir_Rep={y}_CIP13")
            link = next((l for l in re.findall(r'href="([^"]+)"', page.text) if l.endswith(f"NB_{y}_cip13.CSV.gz")), None)
            if link:
                year = y
                break
        if not year:
            add_gap(conn, "market", "country", "FR", "Open Medic CIP13 file not found on the download page", "https://open-data-assurance-maladie.ameli.fr/medicaments/", "FR Open Medic")
        else:
            url = "https://open-data-assurance-maladie.ameli.fr/medicaments/" + link.lstrip("./")
            g, raw = om.get(url)
            stable_url = f"https://open-data-assurance-maladie.ameli.fr/medicaments/download2.php?Dir_Rep={year}_CIP13 (NB_{year}_cip13.CSV.gz)"
            close(conn, "market_metric", "country='FR' AND source_name='FR Open Medic'", ())
            rows = []
            for row in csv.DictReader(io.StringIO(gzip.decompress(g.content).decode("latin-1")), delimiter=";"):
                cip = (row.get("CIP13") or "").strip()
                pid = cip_to_pid.get(cip)
                for metric, col, unit in (("reimbursed_packs", "BOITES", "packs"), ("reimbursed_amount", "REM", "EUR"), ("reimbursement_base", "BSE", "EUR")):
                    v = num(row.get(col))
                    if v is not None:
                        rows.append((None, "FR", metric, unit, str(year), v, pid, cip, stable_url, "FR Open Medic", now(), raw))
            with conn.cursor() as cur:
                cur.executemany("""INSERT INTO market_metric (api_id, country, metric, unit, period, value, product_id, pack_code, source_url,
                                   source_name, retrieved_at, status, raw_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'official',%s)""", rows)
            st["open_medic_rows"] = len(rows)
            st["open_medic_linked_packs"] = len({r[7] for r in rows if r[6]})
            st["open_medic_year"] = year
        print("FR market", dict(st), flush=True)


def fr_shortages():
    """ANSM 'disponibilité des produits de santé' list -> event(shortage) per matched API."""
    st = defaultdict(int)
    with connect() as conn:
        f = Fetcher(conn, "FR ANSM Ruptures", raw_dir="ansm")
        m = SubstanceMatcher(conn)
        url = "https://ansm.sante.fr/disponibilites-des-produits-de-sante/medicaments"
        r, raw = f.get(url)
        rows = re.findall(r'<tr class="product-item"[^>]*data-href="([^"]+)"[^>]*>(.*?)</tr>', r.text, re.S)
        conn.execute("UPDATE event SET valid_to=now() WHERE valid_to IS NULL AND event_type='shortage' AND source_name='FR ANSM Ruptures'")
        clean = lambda h: re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", __import__("html").unescape(h))).strip()  # noqa: E731
        for href, tr in rows:
            tds = re.findall(r"<td([^>]*)>(.*?)</td>", tr, re.S)
            if len(tds) < 4:
                continue
            state, date_s, name, back = clean(tds[0][1]), clean(tds[1][1]), clean(tds[2][1]), clean(tds[3][1])
            domain = clean(tds[4][1]) if len(tds) > 4 else None
            st["items"] += 1
            ids = m.match(name) or [None]  # None = market-level event (no pilot API matched), kept for the country view
            resolved = bool(back) or "remise" in state.lower()
            for aid in ids:
                conn.execute("""INSERT INTO event (event_type, event_date, entity_type, entity_ref, detail, source_url, source_name, retrieved_at, status, raw_id)
                                VALUES ('shortage', to_date(%s,'DD/MM/YYYY'), %s, %s, %s::jsonb, %s, 'FR ANSM Ruptures', %s, 'official', %s)""",
                             (date_s if re.match(r"\d{2}/\d{2}/\d{4}$", date_s) else None, "api" if aid else "market", aid,
                              __import__("json").dumps(dict(country="FR", product=name[:200], state=state, active=not resolved,
                                                            back_in_stock=back or None, domain=domain, reporter="ANSM (marketing authorisation holder declaration)")),
                              "https://ansm.sante.fr" + href, now(), raw))
                st["events"] += 1
        print("FR ANSM", dict(st), flush=True)


ES_UNIT_RX = re.compile(r"(\d+)\s*(comprimidos?|c[aá]psulas?|sobres?|ampollas?|viales?|jeringas?|plumas?|parches?|grageas?|supositorios?|"
                        r"cartuchos?|bolsas?|dosis|pastillas?|unidades?)\b", re.I)


def es():
    st = defaultdict(int)
    with connect() as conn:
        register(conn)
        cima = Fetcher(conn, "ES AEMPS CIMA REST", raw_dir="cima_presentaciones")
        prod = dict(conn.execute("SELECT authorisation_no, product_id FROM product WHERE valid_to IS NULL AND natural_key LIKE 'ES|%%'").fetchall())
        cn_reg, gen, page = {}, {}, 1
        while True:
            r, _ = cima.get("https://cima.aemps.es/cima/rest/presentaciones", params={"pagina": page})
            if r.status_code != 200:
                add_gap(conn, "market", "country", "ES", f"CIMA presentaciones page {page}: HTTP {r.status_code}", "https://cima.aemps.es/cima/rest/presentaciones", "ES AEMPS CIMA REST")
                break
            j = r.json()
            for it in j.get("resultados", []):
                cn_reg[str(it.get("cn"))] = str(it.get("nregistro"))
                gen[str(it.get("nregistro"))] = bool(it.get("generico"))
            if page * j.get("tamanioPagina", 200) >= j.get("totalFilas", 0):
                break
            page += 1
        st["presentations"] = len(cn_reg)
        nf = Fetcher(conn, "ES Nomenclator", raw_dir="es_nomenclator")
        url = "https://www.sanidad.gob.es/profesionales/nomenclator.do?metodo=nomenclatorExcel"
        r, raw = nf.get(url)
        import pandas as pd
        df = pd.read_excel(io.BytesIO(r.content), dtype={"Código Nacional": str})
        close(conn, "price", "country='ES' AND source_name='ES Nomenclator'", ())
        rows = []
        for _, x in df.iterrows():
            cn = str(x["Código Nacional"]).strip().split(".")[0]
            pid = prod.get(cn_reg.get(cn, ""))
            if not pid:
                continue
            name = str(x["Nombre del producto farmacéutico"])
            m = ES_UNIT_RX.search(name)
            u = int(m.group(1)) if m else None
            for col, ptype in (("Precio de venta al público con IVA", "public price incl. VAT (PVP IVA)"), ("Precio de referencia", "reference price (precio de referencia)")):
                v = x.get(col)
                if v is None or v != v:
                    continue
                v = float(v)
                rows.append(("fdf_list", pid, "ES", name[:300], v, "EUR", ptype, u, "unit" if u else None, round(v / u, 4) if u else None,
                             cn, str(x.get("Aportación del beneficiario") or "") or None, url, "ES Nomenclator", now(), raw))
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO price (level, product_id, country, pack_text, value, currency, price_type, units_per_pack, unit,
                               normalized_value, pack_code, reimbursement_rate, source_url, source_name, retrieved_at, status, raw_id)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'official',%s)""", rows)
        st["prices"] = len(rows)
        st["priced_products"] = len({r[1] for r in rows})
        close(conn, "product_generic", "source_name='ES AEMPS CIMA REST'", ())
        g = [(prod[reg], None, None, "generic", "https://cima.aemps.es/cima/rest/presentaciones", "ES AEMPS CIMA REST", now())
             for reg, isg in gen.items() if isg and reg in prod]
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO product_generic (product_id, group_id, group_label, generic_type, source_url, source_name, retrieved_at)
                               VALUES (%s,%s,%s,%s,%s,%s,%s)""", g)
        st["generic_flags"] = len(g)
        add_gap(conn, "market", "country", "ES", "No public dispensing volume per pack for Spain (Ministry publishes aggregated billing only)",
                "https://www.sanidad.gob.es/profesionales/farmacia/datos/home.htm", "ES Nomenclator")
        print("ES market", dict(st), flush=True)


def dk():
    st = defaultdict(int)
    with connect() as conn:
        register(conn)
        f = Fetcher(conn, "DK Medicinpriser", raw_dir="dk_medicinpriser")
        page_url = "https://sundhedsdatabank.dk/medicin/medicinpriser-menu/medicinpriser"
        page, _ = f.get(page_url)
        link = next(iter(re.findall(r'href="([^"]+\.xlsx)"', page.text)), None)
        if not link:
            add_gap(conn, "market", "country", "DK", "Price file link not found on Sundhedsdatabanken page", page_url, "DK Medicinpriser")
            return
        r, raw = f.get(link)
        import pandas as pd
        df = pd.read_excel(io.BytesIO(r.content), "Medicinpriser data", dtype={"Varenummer": str})
        dates = [c for c in df.columns[9:] if re.fullmatch(r"\d{8}(\.0+)?", str(c))]
        last = dates[-1]
        m = SubstanceMatcher(conn)
        prod = {}
        for pid, name in conn.execute("SELECT product_id, name FROM product WHERE valid_to IS NULL AND country='DK'").fetchall():
            prod.setdefault((name or "").strip().lower(), pid)
        close(conn, "price", "country='DK' AND source_name='DK Medicinpriser'", ())
        rows = []
        piv = df[df["Indikator"].isin(["AIP", "AUP"])]
        for (vnr, ind), x in piv.groupby(["Varenummer", "Indikator"]):
            x = x.iloc[0]
            aids = m.match(f"{x['Indholdsstof']} {x['Lægemiddel']}")
            pid = prod.get(str(x["Lægemiddel"]).strip().lower())
            pack = f"{x['Lægemiddel']} {x['Styrke']} {x['Form']}, {x['Pakning']} ({x['Firma']})"
            um = re.match(r"(\d+)\s*stk", str(x["Pakning"]))
            u = int(um.group(1)) if um else None
            ptype = "pharmacy purchase price (AIP)" if ind == "AIP" else "consumer price incl. VAT (AUP)"
            hist = dates if (aids and ind == "AUP") else [last]
            for dcol in hist:
                v = x.get(dcol)
                if v is None or v != v:
                    continue
                rows.append(("fdf_list", (aids or [None])[0], pid, "DK", pack[:300], float(v), "DKK", ptype, u, "unit" if u else None,
                             round(float(v) / u, 4) if u else None, str(dcol)[:8], str(vnr), link, "DK Medicinpriser", now(), raw))
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO price (level, api_id, product_id, country, pack_text, value, currency, price_type, units_per_pack, unit,
                               normalized_value, price_date, pack_code, source_url, source_name, retrieved_at, status, raw_id)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,to_date(%s,'YYYYMMDD'),%s,%s,%s,%s,'official',%s)""", rows)
        st["price_rows"] = len(rows)
        st["packs"] = int(piv["Varenummer"].nunique())
        st["linked_products"] = len({r[2] for r in rows if r[2]})
        st["pilot_api_rows"] = sum(1 for r in rows if r[1])
        st["latest"] = str(last)[:8]
        add_gap(conn, "market", "country", "DK", "Medstat volume data is only offered as an interactive application on Sundhedsdatabanken; no file download for automated use",
                "https://sundhedsdatabank.dk/medicin/aarlige-opgoerelser-medstat", "DK Medstat")
        print("DK market", dict(st), flush=True)


if __name__ == "__main__":
    {"fr": fr, "fr_shortages": fr_shortages, "es": es, "dk": dk}[sys.argv[1]]()
