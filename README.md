# PharmaLens

Verknüpfter Graph aller Wirkstoffe (APIs) im Markt – Hersteller, Zulassungen, Leaflet-Hersteller, Patente, Engpässe, Tender, Supply Chain. Jeder Datenpunkt mit Quelle, Status (`official` / `secondary` / `derived` / `gap`) und Versionierung (`valid_from` / `valid_to`).

## Struktur
| Ordner | Inhalt |
|---|---|
| `connectors/` | ein Connector pro Quelle (EMA, BDPM, CIMA, Swissmedic, AIFA, Drugs@FDA, FDA DMF, Orange Book, TED, …) |
| `enrich/` | Leaflet-Parser, GLEIF, Reparse aus Rohspeicher |
| `resolve/` | Entity Resolution Firmen |
| `graph/` | Supply Chain, API-Zusammenfassungen, CSV-Export |
| `qa/` | Quellenprüfung (Phase 0), QA-Regeln, Live-Stichprobenverifikation |
| `models/` | Schema, Pilotliste, Länder, DB-Helfer |
| `db/` | DB-Snapshot (Schema + Daten) und Supabase-Loader |
| `reports/` | Phase-0-Quellenbericht, Pilotbericht, CSV-Exporte |
| `tests/` | 24 Tests (u. a. Konkurrenzfehler: GE≠DE, DMF-Agent-Land, Zwischenprodukte, Importeure) |

## Setup
    pip install httpx "psycopg[binary]" pandas openpyxl pypdf pytest
    createdb pharmalens && psql pharmalens -f db/schema_dump.sql
    gunzip -c db/data_dump.sql.gz | psql pharmalens
    PHARMALENS_DSN=postgresql://... python -m pytest tests

Rohdateien (`raw/`) sind nicht versioniert; Index mit SHA-256 in Tabelle `raw_object`.
Produktiv-DB: Supabase (RLS auf allen Tabellen aktiv).
