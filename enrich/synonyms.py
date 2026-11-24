"""Multilingual API synonyms.

1. GSRS names (official): every name of the base substance and its salts, with GSRS language codes, read from the
   raw store (no new download).
2. Register spellings (derived): the substance strings national registers actually use, linked to the API by our
   matcher; kept with how often and where they were seen, so national matching can be audited and improved.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import ROOT  # noqa: E402
from models.db import SubstanceMatcher, connect, norm_text, now  # noqa: E402

GSRS = "FDA GSRS / UNII"


def upsert(conn, aid, syn, kind, lang, n, url, src, status):
    key = norm_text(syn)
    if not key or len(key) > 300:
        return 0
    cur = conn.execute("SELECT syn_id, n_observed FROM api_synonym WHERE api_id=%s AND synonym_norm=%s AND kind=%s AND valid_to IS NULL",
                       (aid, key, kind)).fetchone()
    if cur:
        if (cur[1] or 0) != (n or 0):
            conn.execute("UPDATE api_synonym SET valid_to=now() WHERE syn_id=%s", (cur[0],))
        else:
            return 0
    conn.execute("""INSERT INTO api_synonym (api_id, synonym, synonym_norm, lang, kind, n_observed, source_url, source_name,
                    retrieved_at, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                 (aid, syn, key, lang, kind, n, url, src, now(), status))
    return 1


def run():
    st = dict(gsrs_names=0, register_spellings=0)
    with connect() as conn:
        base = {unii: aid for aid, unii in conn.execute(
            "SELECT api_id, unii FROM api WHERE valid_to IS NULL AND parent_api_id IS NULL").fetchall()}
        salt_parent = {unii: (pid, salt) for unii, pid, salt in conn.execute(
            "SELECT unii, parent_api_id, salt_form FROM api WHERE valid_to IS NULL AND parent_api_id IS NOT NULL").fetchall()}
        # 1) GSRS names from raw store
        for path, url in conn.execute("""SELECT r.path, r.url FROM raw_object r JOIN source s USING (source_id)
                                         WHERE s.name=%s ORDER BY r.raw_id""", (GSRS,)).fetchall():
            try:
                data = json.loads((ROOT / path).read_text())
            except (ValueError, FileNotFoundError):
                continue
            recs = data.get("content", []) if isinstance(data, dict) and "content" in data else [data]
            for rec in recs:
                unii = rec.get("approvalID")
                aid = base.get(unii) or (salt_parent.get(unii) or (None,))[0]
                if not aid:
                    continue
                kind = "inn" if unii in base else "salt"
                for n in rec.get("names", []):
                    nm = n.get("name", "")
                    lang = ",".join(n.get("languages") or []) or None
                    k = "inn" if kind == "inn" and re.search(r"\[INN\]|\[WHO-DD\]", nm) else ("salt" if kind == "salt" else "name")
                    st["gsrs_names"] += upsert(conn, aid, re.sub(r"\s*\[[^\]]+\]\s*$", "", nm).strip() or nm, k, lang, None,
                                               url.split("?")[0], GSRS, "official")
        # 2) register spellings as observed
        rules = dict(SubstanceMatcher(conn).rules)  # api_id -> regex
        obs = defaultdict(lambda: [0, set()])
        for aid, raw, src in conn.execute("""SELECT pa.api_id, pa.substance_raw, p.source_name FROM product_api pa
                                             JOIN product p ON p.product_id=pa.product_id AND p.valid_to IS NULL""").fetchall():
            if src in ("DK DKMA",):  # register gives product names only, no substance field
                continue
            if src.startswith("ES AEMPS"):  # CIMA text = "<vtm, lower case> <PRODUCT NAME>": keep the vtm part only
                m = re.match(r"^[a-záéíóúñü ,]+(?= [A-ZÁÉÍÓÚÑ]|$)", raw or "")
                raw = (m.group(0) if m else "").replace(" y ", " + ")
            for part in re.split(r"\s*(?:\|\||\||;|#|\+|/|,(?=\s*[A-ZÄÖÜa-z]))\s*", raw or ""):
                part = re.sub(r"\s+\d[\d.,]*\s*(mg|g|µg|mcg|ui|iu|%).*$", "", part, flags=re.I).strip()
                if 3 <= len(part) <= 120 and aid in rules and rules[aid].search(norm_text(part)):
                    o = obs[(aid, part)]
                    o[0] += 1
                    o[1].add(src)
        for (aid, part), (n, srcs) in obs.items():
            st["register_spellings"] += upsert(conn, aid, part, "register_spelling", None, n,
                                               "internal:enrich/synonyms.py", "; ".join(sorted(srcs))[:200], "derived")
        print("synonyms", st, conn.execute("SELECT kind, count(*) FROM api_synonym WHERE valid_to IS NULL GROUP BY 1").fetchall())


if __name__ == "__main__":
    run()
