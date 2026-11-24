"""Phase 8 QA rules. Each rule returns (name, violations, total, detail). Results -> reports/qa_pilot.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.common import ROOT  # noqa: E402
from models.db import connect  # noqa: E402

PROV_TABLES = ["api", "company", "company_relation", "api_certificate", "product", "product_manufacturer", "patent", "event",
               "tender", "supply_link", "api_synonym", "company_alias", "company_role", "signal", "potential_customer"]


def rules(conn):
    out = []
    for t in PROV_TABLES:
        v, n = conn.execute(f"""SELECT count(*) FILTER (WHERE source_url IS NULL OR source_url='' OR source_name IS NULL
                                 OR retrieved_at IS NULL OR status IS NULL), count(*) FROM {t}""").fetchone()
        out.append((f"provenance:{t}", v, n, "Zeile ohne source_url/source_name/retrieved_at/status"))
    v, n = conn.execute("""SELECT count(*) FILTER (WHERE status<>'derived' OR rationale IS NULL OR cardinality(evidence_ids)=0),
                           count(*) FROM company_role WHERE valid_to IS NULL AND role='cdmo'""").fetchone()
    out.append(("cdmo_role_derived_with_evidence", v, n, "CDMO-Rolle muss derived sein, mit Begründung und Belegen"))
    v, n = conn.execute("""SELECT count(*) FILTER (WHERE auth_date < '1900-01-01' OR auth_date > now()::date), count(auth_date)
                           FROM product WHERE valid_to IS NULL""").fetchone()
    out.append(("auth_date_plausible", v, n, "Zulassungsdatum vor 1900 oder in der Zukunft"))
    v, n = conn.execute("""SELECT count(*) FILTER (WHERE kind='register_spelling' AND status<>'derived'), count(*)
                           FROM api_synonym WHERE valid_to IS NULL""").fetchone()
    out.append(("register_spelling_is_derived", v, n, "beobachtete Schreibweisen sind abgeleitet"))
    v, n = conn.execute("""SELECT count(*) FILTER (WHERE status<>'derived' OR cardinality(reasons)=0 OR cardinality(evidence_ids)=0),
                           count(*) FROM potential_customer WHERE valid_to IS NULL""").fetchone()
    out.append(("potential_customer_derived_with_reasons", v, n, "Kunden-Hinweis nur abgeleitet, mit Gründen und Belegen"))
    v, n = conn.execute("""SELECT count(*) FILTER (WHERE source_url IS NULL OR cardinality(evidence_ids)=0 OR signal_date IS NULL),
                           count(*) FROM signal WHERE valid_to IS NULL""").fetchone()
    out.append(("signal_has_date_source_evidence", v, n, "Signal ohne Datum, Quelle oder Beleg"))
    v, n = conn.execute("SELECT count(*) FILTER (WHERE country IS NULL), count(*) FROM company WHERE valid_to IS NULL").fetchone()
    out.append(("company_without_country", v, n, "Firma ohne Land (nicht erfunden -> gap)"))
    v = conn.execute("SELECT count(*) FROM (SELECT name_normalized FROM company WHERE valid_to IS NULL GROUP BY 1 HAVING count(*)>1) x").fetchone()[0]
    out.append(("duplicate_company_after_ER", v, conn.execute("SELECT count(*) FROM company WHERE valid_to IS NULL").fetchone()[0],
                "gleicher legal_key mehrfach aktiv"))
    v, n = conn.execute("SELECT count(*) FILTER (WHERE expiry < '1985-01-01' OR expiry > '2050-12-31'), count(*) FROM patent").fetchone()
    out.append(("patent_expiry_plausible", v, n, "Ablauf ausserhalb 1985-2050"))
    v, n = conn.execute("""SELECT count(*) FILTER (WHERE evidence_quote IS NULL OR position(split_part(manufacturer_raw,' ',1) IN evidence_quote)=0),
                           count(*) FROM product_manufacturer WHERE valid_to IS NULL""").fetchone()
    out.append(("manufacturer_quote_contains_name", v, n, "Zitat fehlt oder enthält den Herstellernamen nicht"))
    v, n = conn.execute("""SELECT count(*) FILTER (WHERE country IS NOT NULL AND country_basis NOT LIKE 'GLEIF%%'
                              AND country_basis NOT LIKE 'derived: alle Leaflet%%'), count(*) FROM company WHERE valid_to IS NULL
                              AND 'api_manufacturer' = ANY(roles)""").fetchone()
    out.append(("dmf_holder_country_not_from_dmf", v, n, "Land eines API-Herstellers aus anderer Quelle als GLEIF/Leaflet-Standort (US-Agent-Fehler der DMF-Liste)"))
    v, n = conn.execute("""SELECT count(*) FILTER (WHERE 'api_manufacturer'=ANY(c.roles) AND NOT EXISTS (
                              SELECT 1 FROM api_certificate a WHERE a.holder_company_id=c.company_id AND a.valid_to IS NULL)
                              AND NOT EXISTS (SELECT 1 FROM product_manufacturer m WHERE m.company_id=c.company_id
                              AND m.role='api_manufacturer' AND m.valid_to IS NULL)), count(*) FROM company c WHERE c.valid_to IS NULL""").fetchone()
    out.append(("api_role_only_from_api_evidence", v, n, "API-Hersteller-Rolle ohne Zertifikat/Annex-IIA-Beleg (Importeur-Fehler)"))
    v, n = conn.execute("SELECT count(*) FILTER (WHERE confidence<>'confirmed' AND status<>'derived'), count(*) FROM supply_link").fetchone()
    out.append(("derived_links_marked_derived", v, n, "nicht bestätigte Verbindung ohne status=derived"))
    v, n = conn.execute(r"""SELECT count(*) FILTER (WHERE evidence_quote ~* '[A-Z0-9._%%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}'), count(*)
                            FROM product_manufacturer WHERE valid_to IS NULL""").fetchone()
    out.append(("no_email_in_quotes", v, n, "E-Mail-Adresse im Zitat (DSGVO-Prüfung)"))
    v, n = conn.execute("SELECT count(*) FILTER (WHERE site_country IS NULL), count(*) FROM product_manufacturer WHERE valid_to IS NULL").fetchone()
    out.append(("manufacturer_site_country", v, n, "Standort ohne bestimmbares Land"))
    v, n = conn.execute("""SELECT count(*) FILTER (WHERE lower(mah_raw) IN ('nan','none','null') OR lower(name) IN ('nan','none')),
                           count(*) FROM product WHERE valid_to IS NULL""").fetchone()
    out.append(("no_nan_literals", v, n, "Fehlwert als Text 'NaN'/'None' gespeichert"))
    v = conn.execute("SELECT count(*) FROM company WHERE valid_to IS NULL AND split_part(name_normalized,'|',1) IN ('NAN','NONE','NULL')").fetchone()[0]
    out.append(("no_nan_company", v, 1, "Scheinfirma aus Fehlwert"))
    return out


def run():
    with connect() as conn:
        res = [dict(rule=r, violations=v, total=n, description=d) for r, v, n, d in rules(conn)]
    (ROOT / "reports" / "qa_pilot.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    for r in res:
        print(f"{'OK ' if r['violations'] == 0 else 'XX '} {r['rule']:38} {r['violations']:>6} / {r['total']}")
    return res


if __name__ == "__main__":
    run()
