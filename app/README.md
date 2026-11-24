# PharmaLens Explorer (Pilot-UX)

- `index.html`: klickbare App im PharmaLens-Corporate-Layout (Inter, Navy #0B1A3A, Blau #2457E6, Status-Chips Official/Derived/Gap), hell/dunkel.
- Daten: `apis.json` (Übersicht) + `api/<inn>.json` (Details, beim Öffnen nachgeladen), erzeugt aus der PharmaLens-DB.
- Live: privates Claude-Artifact `https://claude.ai/artifact/3F3Q5k2BR5kMDDEANUWqiq`.
- Die JSON-Daten werden nicht versioniert (abgeleitet, ~9.5 MB); Neuerzeugung über den Export im Session-Verlauf bzw. künftig `graph/export_app.py`.
