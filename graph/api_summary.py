"""Phase 8 output: one-sentence summary per API + CSV export per table (each row with its source)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import ROOT  # noqa: E402
from models.db import connect  # noqa: E402

OUT = ROOT / "reports" / "pilot_export"

EXPORTS = {
    "api": "SELECT inn, salt_form, unii, cas, atc, status, source_url FROM api WHERE valid_to IS NULL ORDER BY inn, salt_form NULLS FIRST",
    "hersteller_zertifikate": """SELECT a.inn, c.cert_type, c.number, c.cert_status, c.issue_date, c.holder_raw, co.country holder_country,
                                 co.country_basis, c.substance_raw, c.status, c.source_url FROM api_certificate c JOIN api a ON a.api_id=c.api_id
                                 AND a.valid_to IS NULL LEFT JOIN company co ON co.company_id=c.holder_company_id AND co.valid_to IS NULL
                                 WHERE c.valid_to IS NULL ORDER BY 1,2,3""",
    "zulassungen": """SELECT a.inn, p.country, p.name, p.mah_raw, p.authorisation_no, p.strength, p.form, p.procedure, p.product_status,
                      p.is_veterinary, p.status, p.source_name, p.source_url FROM product p JOIN product_api pa USING (product_id)
                      JOIN api a ON a.api_id=pa.api_id WHERE p.valid_to IS NULL ORDER BY 1,2,3""",
    "fertigprodukt_hersteller": """SELECT a.inn, p.country, p.name product, pm.role, pm.manufacturer_raw, pm.site_address_raw, pm.site_country,
                                   pm.country_basis, pm.evidence_quote, pm.leaflet_url, pm.status, pm.source_url FROM product_manufacturer pm
                                   JOIN product p ON p.product_id=pm.product_id AND p.valid_to IS NULL JOIN product_api pa ON pa.product_id=p.product_id
                                   JOIN api a ON a.api_id=pa.api_id WHERE pm.valid_to IS NULL ORDER BY 1,2,3""",
    "patente": """SELECT a.inn, p.jurisdiction, p.number, p.patent_type, p.expiry, p.patent_status, p.legal_events, p.status, p.source_url
                  FROM patent p JOIN api a ON a.api_id=p.api_id WHERE p.valid_to IS NULL ORDER BY 1,5""",
    "engpaesse": """SELECT a.inn, e.event_date, e.detail, e.status, e.source_url FROM event e JOIN api a ON a.api_id=e.entity_ref
                    WHERE e.event_type='shortage' AND e.valid_to IS NULL ORDER BY 1,2""",
    "tender": """SELECT a.inn, t.notice_id, t.award_date, t.buyer, t.winner_raw, t.value, t.currency, t.status, t.source_url FROM tender t
                 JOIN api a ON a.api_id=t.api_id ORDER BY 1,3 DESC""",
    "supply_chain": """SELECT a.inn, s.link_type, s.confidence, co.name_raw[1] company, co.country, p.country market, p.name product,
                       s.rationale, s.status, s.source_url FROM supply_link s JOIN company co ON co.company_id=s.from_id AND co.valid_to IS NULL
                       JOIN product p ON p.product_id=s.to_id AND p.valid_to IS NULL JOIN product_api pa ON pa.product_id=p.product_id
                       JOIN api a ON a.api_id=pa.api_id WHERE s.confidence<>'hypothesis' ORDER BY 1,2""",
    "firmen": """SELECT company_id, name_normalized, array_to_string(name_raw,' | ') name_raw, country, country_basis, lei,
                 array_to_string(roles, ',') roles, status, source_url FROM company WHERE valid_to IS NULL ORDER BY 2""",
    "konzernstruktur": """SELECT c.name_raw[1] child, p.name_raw[1] parent, r.relation_type, r.status, r.source_url FROM company_relation r
                          JOIN company c ON c.company_id=r.child_id AND c.valid_to IS NULL JOIN company p ON p.company_id=r.parent_id
                          AND p.valid_to IS NULL WHERE r.valid_to IS NULL""",
    "luecken": "SELECT area, entity_type, entity_ref, reason, where_obtainable, source_name FROM gap WHERE resolved_at IS NULL ORDER BY 1,3",
}


def summaries(conn):
    rows = conn.execute("""
      WITH a AS (SELECT api_id, inn FROM api WHERE parent_api_id IS NULL AND valid_to IS NULL),
      cert AS (SELECT api_id, count(DISTINCT holder_company_id) FILTER (WHERE cert_type='US_DMF' AND cert_status='active') dmf_act,
                      count(DISTINCT holder_company_id) FILTER (WHERE cert_type='US_DMF') dmf_all,
                      count(*) FILTER (WHERE cert_type='WHO_PQ') who FROM api_certificate WHERE valid_to IS NULL GROUP BY 1),
      bio AS (SELECT pa.api_id, count(DISTINCT pm.company_id) n FROM product_manufacturer pm JOIN product_api pa USING (product_id)
              WHERE pm.role='api_manufacturer' AND pm.valid_to IS NULL GROUP BY 1),
      prod AS (SELECT pa.api_id, count(DISTINCT p.product_id) n, count(DISTINCT p.country) FILTER (WHERE p.country<>'EU') c,
                      count(DISTINCT p.mah_company_id) mah, bool_or(p.country='EU') central
               FROM product p JOIN product_api pa USING (product_id) WHERE p.valid_to IS NULL GROUP BY 1),
      site AS (SELECT pa.api_id, count(DISTINCT pm.company_id) n, count(DISTINCT pm.product_id) prods
               FROM product_manufacturer pm JOIN product_api pa USING (product_id) WHERE pm.role='batch_release' AND pm.valid_to IS NULL GROUP BY 1),
      pat AS (SELECT api_id, max(expiry) FILTER (WHERE patent_type='substance') sub, max(expiry) FILTER (WHERE patent_type NOT LIKE '%%combination%%') anyp,
              max(expiry) FILTER (WHERE patent_type LIKE '%%combination%%') combo
              FROM patent WHERE jurisdiction='US' AND valid_to IS NULL GROUP BY 1),
      sh AS (SELECT entity_ref api_id, count(*) n FROM event WHERE event_type='shortage' AND valid_to IS NULL
             AND coalesce(detail->>'active','true') <> 'false' AND coalesce(detail->>'state','') <> 'Resolved' GROUP BY 1)
      SELECT a.inn, coalesce(cert.dmf_act,0), coalesce(cert.dmf_all,0), coalesce(cert.who,0), coalesce(bio.n,0), coalesce(prod.n,0),
             coalesce(prod.c,0), coalesce(prod.mah,0), coalesce(prod.central,false), coalesce(site.n,0), coalesce(site.prods,0),
             pat.sub, pat.anyp, pat.combo, coalesce(sh.n,0)
      FROM a LEFT JOIN cert USING (api_id) LEFT JOIN bio USING (api_id) LEFT JOIN prod USING (api_id) LEFT JOIN site USING (api_id)
      LEFT JOIN pat USING (api_id) LEFT JOIN sh USING (api_id) ORDER BY a.inn""").fetchall()
    out = []
    import datetime as _dt
    today = _dt.date.today()

    def d(x):
        return f"{x} (abgelaufen)" if x and x < today else str(x)
    for inn, dmf_act, dmf_all, who, bio, n, c, mah, central, sites, sprods, sub, anyp, combo, sh in rows:
        us_pat = f"US-Substanzpatent bis {d(sub)}" if sub else (f"US-Patente (Formulierung/Verwendung) bis {d(anyp)}" if anyp else "kein US-Patent auf Monopräparaten im Orange Book")
        if combo:
            us_pat += f" (Patente auf Kombinationspräparaten bis {d(combo)}, separat geführt)"
        s = (f"{inn.capitalize()}: {dmf_act} API-Hersteller mit aktivem US-DMF ({dmf_all} gesamt)"
             f"{f', {who} WHO-PQ' if who else ''}{f', {bio} bestätigte API-Hersteller aus EMA Annex IIA' if bio else ''}, CEP: keine Daten; "
             f"zugelassen in {c} Ländern{' plus EU-zentral' if central else ''} ({n} Produkte, {mah} MAHs); "
             f"{sites} Batch-Release-Firmen aus {sprods} Leaflets; {us_pat}, EU-Patent/SPC: keine Daten; "
             f"{sh} offene Engpassmeldungen (EU zentral + ES); EU-DMF-Hinweis: noch keine Datengrundlage.")
        out.append(dict(inn=inn, summary=s))
    return out


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        for name, sql in EXPORTS.items():
            cur = conn.execute(sql)
            cols = [d.name for d in cur.description]
            with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(cols)
                for r in cur:
                    w.writerow([json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else v for v in r])
        s = summaries(conn)
    (OUT / "zusammenfassung.json").write_text(json.dumps(s, indent=2, ensure_ascii=False))
    for x in s:
        print(x["summary"])
    return s


if __name__ == "__main__":
    run()
