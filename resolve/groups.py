"""Brand grouping of legal entities (first release): 'nicht bestätigt' = status derived.

Rule: legal entities sharing a distinctive brand stem (first token, or first two tokens when the first is generic)
are linked to a brand-group entity via company_relation(relation_type='brand_group_member', status='derived').
Never merges legal entities. GLEIF parent relations (official) are kept untouched and take precedence in the UI.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.db import connect, new_id, now, upsert_versioned  # noqa: E402

GENERIC = {"LABORATORIOS", "LABORATORIO", "LABORATOIRES", "LABORATOIRE", "LABORATORIES", "LABORATORY", "LAB", "LABS",
           "PHARMA", "PHARMACEUTICALS", "PHARMACEUTICAL", "PHARMACEUTICA", "FARMACEUTICA", "FARMA", "PHARM", "MEDICAL",
           "GENERICS", "GENERIC", "INDUSTRIA", "INDUSTRIES", "HEALTHCARE", "HEALTH", "THE", "DR", "INTERNATIONAL", "GROUP",
           "ZENTIVA_", "BIO", "CHEMICAL", "CHEMICALS", "LIFE", "SCIENCES", "NORTH", "SOUTH", "EURO", "EUROPE", "NEW", "GLOBAL",
           "UNITED", "FIRST", "BEST", "GENERAL", "SPECIALTY", "SPECIALITY", "INSTITUTO", "INSTITUT", "CENTRO", "S", "A", "LA", "LE",
           "EL", "DE", "DES", "GMBH", "AG", "SA", "SL", "SPA", "LTD", "BV", "NV", "INC", "LLC"}
GEO = {"ZHEJIANG", "JIANGSU", "SHANDONG", "HUBEI", "HEBEI", "SHANGHAI", "BEIJING", "GUANGDONG", "SICHUAN", "HANGZHOU",
       "ANHUI", "JIANGXI", "HUNAN", "HENAN", "TIANJIN", "CHONGQING", "SHENZHEN", "FUJIAN", "SHANXI", "SHAANXI", "LIAONING",
       "JILIN", "YUNNAN", "GUANGXI", "CHANGZHOU", "TAIZHOU", "NANJING", "SUZHOU", "WUHAN", "QILU", "INNER", "CHINA", "INDIA",
       "HYDERABAD", "MUMBAI", "GUJARAT", "AHMEDABAD", "BANGALORE", "KOREA", "JAPAN", "AMERICAN", "BRITISH", "SWISS"}
GENERIC |= GEO
# same stem, unrelated companies (known homonyms): stem -> [(regex on base name, distinct stem)]
HOMONYMS = {"MERCK": [(r"^MERCK (SHARP|AND CO|& CO|CO)\b|^MSD\b", "MSD (Merck & Co.)"), (r".*", "MERCK KGAA")]}
MIN_STEM = 4


def stem(base: str) -> str | None:
    toks = [t for t in base.split() if t]
    if not toks:
        return None
    if toks[0] in GENERIC:
        if len(toks) < 2 or toks[1] in GENERIC:
            return None
        s = f"{toks[0]} {toks[1]}"
    else:
        s = toks[0]
    if s in HOMONYMS:
        import re
        for rx, alt in HOMONYMS[s]:
            if re.search(rx, base):
                return alt
    return s if len(s.replace(" ", "")) >= MIN_STEM else None


def run():
    with connect() as conn:
        conn.execute("UPDATE company_relation SET valid_to=now() WHERE relation_type='brand_group_member' AND valid_to IS NULL")
        rows = conn.execute("""SELECT company_id, name_normalized FROM company WHERE valid_to IS NULL
                               AND NOT name_normalized LIKE 'GROUP:%%'""").fetchall()
        groups = defaultdict(list)
        for cid, key in rows:
            s = stem(key.split("|")[0])
            if s:
                groups[s].append((cid, key))
        st = dict(groups=0, members=0)
        for s, members in groups.items():
            if len(members) < 2:
                continue
            gkey = f"GROUP:{s}"
            row = conn.execute("SELECT company_id FROM company WHERE name_normalized=%s AND valid_to IS NULL", (gkey,)).fetchone()
            gid = row[0] if row else new_id(conn)
            upsert_versioned(conn, "company", "company_id", gid, dict(
                name_normalized=gkey, name_raw=[s.title()], country=None, country_basis=None, lei=None, roles=["brand_group"],
                source_url="internal:resolve/groups.py", source_name="PharmaLens ER", retrieved_at=now(), status="derived"),
                ["name_normalized", "name_raw", "roles"])
            st["groups"] += 1
            for cid, key in members:
                conn.execute("""INSERT INTO company_relation (parent_id, child_id, relation_type, source_url, source_name,
                                retrieved_at, status) VALUES (%s,%s,'brand_group_member',%s,'PharmaLens ER',%s,'derived')""",
                             (gid, cid, "internal:resolve/groups.py#" + json.dumps(dict(stem=s, rule="gleicher Markenstamm, nicht bestätigt")), now()))
                st["members"] += 1
        print("brand groups", st)
        return st


if __name__ == "__main__":
    run()
