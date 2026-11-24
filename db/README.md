# Datenbank-Snapshot

- `schema_dump.sql` – vollständiges Schema (pg_dump, public)
- `data_dump.sql.gz` – alle Daten als INSERT-Statements (Pilot, 20 APIs)
- Rohdateien (`raw/`, ~480 MB) sind nicht im Git; Ziel: Supabase Storage, Index in Tabelle `raw_object` (SHA-256).

Wiederherstellen (lokal oder Supabase):

    psql "$DATABASE_URL" -f db/schema_dump.sql
    gunzip -c db/data_dump.sql.gz | psql "$DATABASE_URL"

## Rohdateien (Supabase Storage)

- Privater Bucket `raw` im Projekt `kulodmfvlxocvpkyyoiw` (nicht öffentlich, Zugriff nur mit Secret Key).
- Objektpfad = `raw_object.path`, auf ASCII abgebildet (Akzente entfernt, sonstige Sonderzeichen → `_`), siehe `skey()` in `db/raw_to_storage.py`.
- Dateien > 45 MB liegen als `<pfad>.part1..N` plus `<pfad>.parts.json`; zusammensetzen mit `cat`, SHA-256 = Dateiname.
- Upload und Prüfung: `python db/raw_to_storage.py upload` bzw. `verify` (idempotent, überspringt vorhandene Dateien gleicher Grösse).
