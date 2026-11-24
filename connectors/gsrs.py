"""FDA GSRS connector -> api (base substances + salt forms).

Primary keys: UNII. Codes taken: CAS, WHO-ATC, WHO-VATC, INN, EVMPD, DRUG CENTRAL, PUBCHEM.
Salts come from the GSRS relationship 'SALT/SOLVATE->PARENT' and are stored with parent_api_id.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import Fetcher  # noqa: E402
from models.db import add_gap, connect, new_id, now, upsert_versioned  # noqa: E402
from models.pilot import GSRS_NAME, PILOT  # noqa: E402

SRC = "FDA GSRS / UNII"
API = "https://gsrs.ncats.nih.gov/ginas/app/api/v1"
COMPARE = ["inn", "salt_form", "parent_api_id", "cas", "unii", "atc", "drugcentral_id", "pubchem_cid", "synonyms", "is_veterinary"]


def codes(rec, system):
    return sorted({c["code"] for c in rec.get("codes", []) if c["codeSystem"] == system and c.get("type", "PRIMARY") == "PRIMARY"})


def first_int(vals):
    for v in vals:
        try:
            return int(v)
        except ValueError:
            pass
    return None


def api_id_for_unii(conn, unii):
    row = conn.execute("SELECT api_id FROM api WHERE unii=%s AND valid_to IS NULL", (unii,)).fetchone()
    return row[0] if row else new_id(conn)


SALT_WORDS = {"sodium", "potassium", "calcium", "magnesium", "zinc", "lithium", "hydrochloride", "dihydrochloride",
              "hydrobromide", "bromide", "chloride", "iodide", "acetate", "besylate", "besilate", "mesylate", "mesilate",
              "maleate", "fumarate", "tartrate", "citrate", "succinate", "tosylate", "camsylate", "benzoate", "sulfate",
              "phosphate", "lysine", "arginine", "anhydrous", "monohydrate", "dihydrate", "trihydrate", "hemihydrate",
              "sesquihydrate", "hydrate", "(trihydrate)", "strontium", "nitrate", "lactate", "gluconate", "hyclate"}


def is_salt_name(name: str, base: str) -> bool:
    n, b = name.lower().split(), base.lower().split()
    return n[:len(b)] == b and len(n) > len(b) and all(w in SALT_WORDS for w in n[len(b):])


def write(conn, rec, inn, salt_form, parent_id, is_vet, url, raw_id, status="official"):
    unii = rec["approvalID"]
    aid = api_id_for_unii(conn, unii)
    atc = codes(rec, "WHO-ATC") + codes(rec, "WHO-VATC")
    vals = dict(inn=inn, salt_form=salt_form, parent_api_id=parent_id, cas=(codes(rec, "CAS") or [None])[0], unii=unii,
                atc=atc or None, drugcentral_id=first_int(codes(rec, "DRUG CENTRAL")),
                pubchem_cid=first_int(codes(rec, "PUBCHEM")),
                synonyms=sorted({n["name"] for n in rec.get("names", [])})[:80] or None, is_veterinary=is_vet,
                source_url=url, source_name=SRC, retrieved_at=now(), status=status, raw_id=raw_id)
    return aid, upsert_versioned(conn, "api", "api_id", aid, vals, COMPARE)


def run():
    stats = dict(base=0, salts=0, errors=0, changes=0)
    with connect() as conn:
        f = Fetcher(conn, SRC)
        for inn, group, _ in PILOT:
            name = GSRS_NAME.get(inn, inn).upper()
            r, raw_id = f.get(f"{API}/substances/search", params={"q": f'root_names_name:"{name}"', "top": 10, "view": "full"})
            hits = [s for s in r.json().get("content", []) if s["_name"].upper() == name] if r.status_code == 200 else []
            if not hits:
                stats["errors"] += 1
                add_gap(conn, "api_master", "api", inn, "GSRS: kein exakter Treffer", "manuell prüfen", SRC)
                print("GAP", inn)
                continue
            base = hits[0]
            url = base["_self"].replace("?view=full", "")
            aid, ch = write(conn, base, inn, None, None, group == "veterinary", url, raw_id)
            stats["base"] += 1
            stats["changes"] += ch != "same"
            # salts/esters/solvates point to the base via ACTIVE MOIETY on their own record
            sr, sraw = f.get(f"{API}/substances/search", params={
                "q": f'root_relationships_relatedSubstance_approvalID:"{base["approvalID"]}"', "top": 50, "view": "full"})
            salts = []
            for srec in sr.json().get("content", []) if sr.status_code == 200 else []:
                if srec.get("approvalID") in (None, base["approvalID"]):
                    continue
                moieties = {x["relatedSubstance"].get("approvalID") for x in srec.get("relationships", [])
                            if x["type"] == "ACTIVE MOIETY"}
                if moieties == {base["approvalID"]}:  # single moiety = salt/ester/solvate; mixtures excluded
                    salts.append(srec["_name"])
                    _, ch = write(conn, srec, inn, srec["_name"], aid, group == "veterinary",
                                  srec["_self"].replace("?view=full", ""), sraw)
                    stats["salts"] += 1
                    stats["changes"] += ch != "same"
            # fallback: name-based salt detection (GSRS moiety curation is incomplete, e.g. omeprazole magnesium)
            nr, nraw = f.get(f"{API}/substances/search", params={"q": base["_name"], "top": 100, "view": "full"})
            seen = {base["approvalID"]} | {x for x in conn.execute(
                "SELECT unii FROM api WHERE parent_api_id=%s AND valid_to IS NULL", (aid,)).fetchall() for x in x}
            for srec in nr.json().get("content", []) if nr.status_code == 200 else []:
                if srec.get("approvalID") and srec["approvalID"] not in seen and is_salt_name(srec["_name"], base["_name"]):
                    seen.add(srec["approvalID"])
                    salts.append(srec["_name"] + " (derived)")
                    _, ch = write(conn, srec, inn, srec["_name"], aid, group == "veterinary",
                                  srec["_self"].replace("?view=full", ""), nraw, status="derived")
                    stats["salts"] += 1
                    stats["changes"] += ch != "same"
            print(f"{inn:18} UNII {base['approvalID']}  salts {len(salts)}")
    print(stats)
    return stats


if __name__ == "__main__":
    run()
