# PharmaLens – Phase 1 Pilotbericht (20 Wirkstoffe)

Stand: 2026-11-24 · alle Zahlen aus der Datenbank, aktive Versionen (`valid_to IS NULL`)

## 1. Was gebaut wurde

| Bereich | Connector / Modul | Zeilen |
|---|---|---|
| Wirkstoff-Stamm | `connectors/gsrs.py` (FDA GSRS) | 20 Basen + 43 Salze/Ester (6 davon `derived` über Namensregel, weil GSRS-Kuratierung lückenhaft) |
| Zulassungen | `connectors/ema.py` (Art. 57, EMA zentral), `connectors/national.py` (FR BDPM, ES CIMA, CH Swissmedic HAM+TAM, IT AIFA, US Drugs@FDA) | 11'471 Produkte in 34 Ländern/Gebieten |
| API-Zertifikate | `connectors/certificates.py` (FDA DMF Typ II, WHO PQ) | 590 US-DMF (46 Zwischenprodukte/Darreichungsformen ausgeschlossen), 0 WHO PQ |
| Fertigprodukt-Hersteller | `connectors/leaflets.py` + `enrich/leaflet_parser.py` (ES CIMA-API, FR BDPM, EMA Annex IIA) | 3'900 Batch-Release-Standorte mit wörtlichem Zitat; 9 API-Hersteller aus Annex IIA (biologisch) |
| Firmen / Konzern | `resolve/companies.py`, `enrich/gleif.py` | 1'659 juristische Einheiten, 516 Auto-Merges, 165 Prüfpaare, 69 LEI, 33 Konzernbeziehungen |
| Patente | `connectors/orange_book.py` | 276 US-Patente (Substanz / Formulierung / Verwendung / auf Kombination getrennt) |
| Engpässe | `connectors/shortages.py` (EMA ESMP, AEMPS) | 26 Meldungen |
| Tender | `connectors/ted.py` | 1'211 Vergabebekanntmachungen (max. 100 je API) |
| Supply Chain | `graph/supply_chain.py` | 3'909 `confirmed`-Verbindungen (Standort → Produkt aus demselben Dokument) |
| QA | `qa/rules.py`, `qa/verify_sample.py`, 24 Tests | siehe 3. |
| Export | `graph/api_summary.py` | `reports/pilot_export/*.csv` + Ein-Satz-Zusammenfassung je API |

Rohspeicher: 3'495 Objekte, 491 MB, SHA-256. Alle Parser-Korrekturen wurden aus dem Rohspeicher neu ausgelesen, ohne neue Downloads; 920 überholte Versionen bleiben als Historie erhalten.

## 2. Abdeckung

| Bereich | Abdeckung |
|---|---|
| Wirkstoff-Stamm | 20/20 |
| Zulassungen | 20/20 mit mindestens einer Zulassung; Human-APIs in 10–33 Ländern; Tier-APIs nur CH + EU-zentral |
| Leaflet-Hersteller | ES 1'416/1'742 (81 %), FR 514/548 (94 %), EMA zentral 43/71 (61 %); DE, IT, CH, NL, AT, Nordics: 0 (keine Quelle angebunden) |
| US-DMF | 16/20 (alle Human-APIs plus Marbofloxacin) |
| CEP | 0/20 (EDQM gesperrt) |
| Patente | nur USA; EU/CH/UK 0/20 (EPO-OPS-Key fehlt) |
| Firmen mit Land | 382/1'659 (23 %); Land nur aus GLEIF oder Leaflet-Standort, nie geraten |
| EU-DMF-Hinweis | 0, weil keines der vier Kriterien im Pilot eine Datenquelle hat |

## 3. Qualität

- Alle Pflichtregeln OK: Provenienz in allen Tabellen, keine Dubletten nach ER, Patentdaten plausibel, Zitat enthält Herstellernamen, keine E-Mails in Zitaten, DMF-Land nie aus DMF-Liste, API-Rolle nur aus API-Belegen, nicht bestätigte Verbindungen als `derived`.
- Offen: 82 von 3'909 Standorten (2 %) ohne bestimmbares Land (Inlandsadresse ohne Länderzeile).
- Stichprobe gegen die Live-Primärquelle, 3 × 50: Endstand 150/150 bestätigt. Verlauf: Die erste Runde fand **einen echten Fehlertyp** (verschmolzene Standorte, falsches Land, z. B. Fundació Dau → PL). Er ist korrigiert, mit Tests abgesichert und neu ausgelesen. Zwei weitere Abweichungen waren Fehler im Prüfskript, ebenfalls korrigiert.

## 4. Konkurrenzfehler – Absicherung

| Fehler | Massnahme | Test |
|---|---|---|
| HQ-Land = Land des DMF-Agenten | Land nur aus GLEIF / Leaflet-Standort | QA-Regel `dmf_holder_country_not_from_dmf` |
| Deutschland als «GE» | keine 2-Buchstaben-Ableitung, nur Ländernamen oder PLZ-Präfix | `test_germany_is_never_georgia` |
| Importeur als API-Lieferant | API-Rolle nur aus DMF/WHO-PQ/Annex IIA; FR-Parallelimporte bewusst Lücke | QA-Regel `api_role_only_from_api_evidence` |
| Zwischenprodukt als API | DMF-Filter (side chain, intermediate inkl. FDA-Tippfehler «INTERMIDIATE») | `test_certificates.py` |
| Formulierungspatent eines Kombipräparats als API-Schutz | Typ `*_on_combination` getrennt | Zusammenfassung Sacubitril |

## 5. Lücken (496 offen, Tabelle `gap`)

ES-Prospekte ohne Hersteller-Sektion (273), CEP (20), Written Confirmations (20), EU-Patente/SPC (20), API→FDF-Lieferant ohne Primärbeleg (19), FR-Parallelimporte (28), EMA Annex IIA nicht parsebar (14), GLEIF-Beziehungen veraltet (11), Türkei-Vollliste, Tierarzneimittel ES/US.
