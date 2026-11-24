# Datenbank-Snapshot

- `schema_dump.sql` – vollständiges Schema (pg_dump, public)
- `data_dump.sql.gz` – alle Daten als INSERT-Statements (Pilot, 20 APIs)
- Rohdateien (`raw/`, ~480 MB) sind nicht im Git; Ziel: Supabase Storage, Index in Tabelle `raw_object` (SHA-256).

Wiederherstellen (lokal oder Supabase):

    psql "$DATABASE_URL" -f db/schema_dump.sql
    gunzip -c db/data_dump.sql.gz | psql "$DATABASE_URL"
