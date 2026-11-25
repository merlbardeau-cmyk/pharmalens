"""English presentation layer for exported texts.

The database keeps its original (German) wording - nothing is overwritten. Exports for the app pass free-text fields
through en(): exact phrases first, then fragment rules. Anything not covered stays as stored, so no text is lost;
untranslated() lists what is left for review.
"""
from __future__ import annotations

import re

EXACT = {
    "AIFA-Listen enthalten nur erstattete Arzneimittel (Klasse A/H)": "AIFA lists only contain reimbursed medicines (class A/H)",
    "API-Lieferant der Fertigprodukte nicht in Primärquelle belegt (für Generika i. d. R. vertraulich; ASMF nicht öffentlich)":
        "API supplier of the finished products not documented in a primary source (usually confidential for generics; ASMF not public)",
    "AT: Produkt zugelassen, aber nicht vermarktet – BASG hinterlegt Platzhalter statt Gebrauchsinformation":
        "AT: product authorised but not marketed – BASG stores a placeholder instead of the package leaflet",
    "CEP nicht abrufbar (EDQM robots.txt/WAF) – Lizenzanfrage offen": "CEP not retrievable (EDQM robots.txt/WAF) – licence request pending",
    "EDQM-CEP-Datenbank: Lizenzanfrage offen, neue CEPs nicht abrufbar": "EDQM CEP database: licence request pending, new CEPs not retrievable",
    "EMA Art.-57-Datei enthält kein Zulassungsdatum": "EMA Art. 57 file contains no authorisation date",
    "EMA: Annex IIA nicht parsebar": "EMA: Annex IIA not parsable",
    "EMA: Product-Information-PDF auf EPAR-Seite nicht gefunden": "EMA: product information PDF not found on EPAR page",
    "EU/CH/UK-Patente und SPC: EPO-OPS-Key fehlt; nationale SPC-Register nicht angebunden":
        "EU/CH/UK patents and SPC: EPO OPS key missing; national SPC registers not connected",
    "EudraGMDP liefert für automatisierte Abfragen keine Treffer": "EudraGMDP returns no results for automated queries",
    "FR Parallelimport: Notice nennt Importeur/Umpacker, nicht den Hersteller – bewusst nicht als Hersteller übernommen":
        "FR parallel import: leaflet names the importer/repackager, not the manufacturer – deliberately not taken as manufacturer",
    "NL Parallelimport: Bijsluiter nennt Importeur/Umpacker – bewusst nicht als Hersteller übernommen":
        "NL parallel import: leaflet names the importer/repackager – deliberately not taken as manufacturer",
    "Hersteller-Sektion nach Parser-Korrektur ohne gültigen Standort": "Manufacturer section has no valid site after parser correction",
    "Host nicht freigegeben": "Host not allowed in network policy",
    "Host nicht freigegeben, URL in Brief fehlt": "Host not allowed in network policy, URL missing in brief",
    "Keine offizielle Online-Quelle im Brief; Behörde (ANPP) zu identifizieren": "No official online source in brief; authority (ANPP) to be identified",
    "NL: keine Bijsluiter-Datei im CBG-Register (z. B. EU-zentral → EMA Annex IIA)": "NL: no leaflet file in the CBG register (e.g. EU-central → EMA Annex IIA)",
    "PDF ist ein Scan ohne Textebene – Hersteller nur per OCR lesbar (nicht automatisiert)":
        "PDF is a scan without text layer – manufacturer only readable via OCR (not automated)",
    "Produktseiten rendern im Browser, die seiteneigene Suche liefert für Produktdokumente 0 Treffer; direkter Zugriff auf die interne Such-API mit eingebettetem Schlüssel bewusst nicht genutzt":
        "Product pages render in the browser, the site search returns 0 hits for product documents; direct use of the internal search API with its embedded key deliberately avoided",
    "SGK-Wochendatei enthält nur Änderungen der EK-4/A-Liste; Vollliste nicht lokalisiert, TİTCK per WAF gesperrt":
        "SGK weekly file only contains changes to the EK-4/A list; full list not located, TİTCK blocked by WAF",
    "Suchformular wird abgeschickt, liefert in dieser Umgebung aber keine Ergebnisse (auch exakter Name/Platzhalter); keine Wirkstoffsuche vorhanden":
        "Search form submits but returns no results in this environment (also exact name/wildcard); no substance search available",
    "Tierarzneimittel ES nur in CIMAVet (Host nicht freigegeben)": "Veterinary medicines ES only in CIMAVet (host not allowed)",
    "Tierarzneimittel US (FDA Green Book) noch nicht angebunden": "Veterinary medicines US (FDA Green Book) not yet connected",
    "Written Confirmations nicht abrufbar (CDSCO blockiert)": "Written Confirmations not retrievable (CDSCO blocks access)",
    "HTML zugänglich": "HTML accessible",
    "HTML zugänglich – Seite JS-gerendert, Playwright nötig": "HTML accessible – page rendered by JavaScript, headless browser needed",
    "API erreichbar (Methode prüfen)": "API reachable (method to be checked)",
    "API-Endpunkt liefert text/html statt JSON/XML": "API endpoint returns text/html instead of JSON/XML",
    "HTTP 403: API erreichbar, Zugang erfordert (kostenlosen) Key/Registrierung": "HTTP 403: API reachable, access requires a (free) key/registration",
    "Werk nicht im Leaflet": "Site not in leaflet",
    "Inhaber unbekannt": "Holder unknown",
    "Markengruppe (Namensstamm)": "Brand group (name stem)",
    "derived: alle Leaflet-Standorte dieser Firma in einem Land": "derived: all leaflet sites of this company are in one country",
    # frequencies
    "einmalig": "one-off", "jährlich": "yearly", "laufend": "continuous", "monatlich": "monthly", "quartalsweise": "quarterly",
    "täglich": "daily", "unbekannt": "unknown", "unregelmässig": "irregular", "wöchentlich": "weekly",
}

RULES = [  # (regex, replacement) applied in order
    (r"^(AT|DK|ES|FR|NL|IT): Hersteller-Abschnitt in (Gebrauchsinformation|Packungsbeilage) nicht gefunden \(HTTP (\d+)\)$", r"\1: manufacturer section not found in package leaflet (HTTP \3)"),
    (r"^ES: Hersteller-Sektion im Prospekt nicht gefunden \(HTTP (\d+)\)$", r"ES: manufacturer section not found in leaflet (HTTP \1)"),
    (r"^DK: Fremstiller-Abschnitt nicht gefunden \(HTTP (\d+)\)$", r"DK: manufacturer (fremstiller) section not found (HTTP \1)"),
    (r"^NL: Fabrikant-Sektion im Bijsluiter nicht gefunden \(HTTP (\d+)\)$", r"NL: manufacturer (fabrikant) section not found in leaflet (HTTP \1)"),
    (r"^(\w\w): Register liefert im genutzten Export kein Zulassungsdatum$", r"\1: register export used provides no authorisation date"),
    (r"^GLEIF (direct|ultimate)-parent: Beziehung (\w+)/(\w+), letzte Aktualisierung ([\d-]+) – nicht übernommen \(möglicherweise veraltet\)$",
     r"GLEIF \1 parent: relationship \2/\3, last update \4 – not used (possibly outdated)"),
    (r"^Direkter Download \((.+), ([\d,]+) Bytes\)$", r"Direct download (\1, \2 bytes)"),
    (r"^Download-Seite mit (\d+) Datei-Links \((.+)\)$", r"Download page with \1 file links (\2)"),
    (r"^API liefert (.+)$", r"API returns \1"),
    (r"^derived: Inlandsadresse ohne Länderzeile im (\w\w)-Leaflet, PLZ-Format (\w\w)$", r"derived: domestic address without country line in \1 leaflet, \2 postcode format"),
    # fragments (status / access / licences)
    (r"HTTP (\d+), robots\.txt verbietet den Pfad", r"HTTP \1, robots.txt disallows the path"),
    (r"HTTP (\d+), technisch erreichbar, aber: ", r"HTTP \1, technically reachable, but: "),
    (r"Authentifizierungs-Weiterleitung \(SSO\) – Login wird nicht verwendet", "authentication redirect (SSO) – no login is used"),
    (r"Nutzungsbedingungen: Datenbanken urheberrechtlich geschützt, Vervielfältigung nur mit schriftlicher Genehmigung – Lizenz nötig",
     "terms of use: databases protected by copyright, reproduction only with written permission – licence needed"),
    (r"CAPTCHA/Bot-Challenge erkannt – wird nicht umgangen", "CAPTCHA/bot challenge detected – not bypassed"),
    (r"HTTP 403: Zugriff verweigert", "HTTP 403: access denied"),
    (r"Web Application Firewall blockiert Cloud-IP/Bot – wird nicht umgangen", "web application firewall blocks cloud IP/bot – not bypassed"),
    (r"^nicht erreichbar: ", "not reachable: "),
    (r"robots\.txt auf (\S+) verbietet alles \(Disallow: /\); Weiterleitung auf (\S+) – Host nicht freigegeben, robots dort ungeprüft",
     r"robots.txt on \1 disallows everything (Disallow: /); redirect to \2 – host not allowed, robots there unchecked"),
    (r"\[zu verifizieren\]", "[to be verified]"), (r"Reuse (erlaubt )?mit Quellenangabe( erlaubt)?", "reuse allowed with attribution"),
    (r"Reuse gemäss EMA Legal Notice mit Quellenangabe", "reuse per EMA legal notice with attribution"),
    (r"Reuse gem\. ", "reuse per "), (r"Reuse erlaubt", "reuse allowed"), (r"frei nutzbar", "free to use"),
    (r"Limit max\. ", "limit max. "), (r"öffentliche Daten, frei", "public data, free"), (r"Rate-Limit beachten", "observe rate limit"),
    (r"Download nur nach Akzeptanz der Nutzungsbedingungen", "download only after accepting the terms of use"),
    (r"Daten NHSBSA unter OGL", "NHSBSA data under OGL"), (r"Datenbank selbst auf (\S+) \(Host nicht freigegeben\)", r"database itself on \1 (host not allowed)"),
    (r"eigentliche AMIce-Recherche läuft über (\S+) \(Proxy blockiert trotz Freigabe\)", r"actual AMIce search runs via \1 (proxy blocks despite allowance)"),
    (r"freie Recherche", "free search"), (r"OGD-Bedingungen", "OGD terms"), (r"DrugCentral-Projekt", "DrugCentral project"),
    (r"systematische Kopie/Weiterverbreitung des Index nur mit Erlaubnis, vollständige Datei kostenpflichtig",
     "systematic copying/redistribution of the index only with permission, full file paid"),
    (r"Produktresuméer separat \(siehe (.+?)\)", r"product summaries separate (see \1)"),
    (r"automatisierte Abfrage eingeschränkt, DPMAconnect kostenpflichtig", "automated queries restricted, DPMAconnect paid"),
    (r"Nutzung der Inhalte eingeschränkt", "use of content restricted"), (r"kostenlose Registrierung \(OAuth Key\), 4 GB/Woche frei", "free registration (OAuth key), 4 GB/week free"),
    (r"kostenloser OAuth-Key", "free OAuth key"), (r"automatisierte Abfrage nur über OPS-Register-Service", "automated queries only via OPS register service"),
    (r"EU-Amt für Veröffentlichungen", "EU Publications Office"), (r"EU-Kommission", "European Commission"),
    (r"Inhalte urheberrechtlich geschützt, systematisches Kopieren untersagt", "content protected by copyright, systematic copying prohibited"),
    (r"NPL-Download-Pfad noch nicht lokalisiert", "NPL download path not yet located"), (r"Stand 2014 \(CNOPS\) – veraltet", "as of 2014 (CNOPS) – outdated"),
    (r"SEC verlangt deklarierten User-Agent mit Kontakt, max\. 10 req/s", "SEC requires a declared user agent with contact, max. 10 req/s"),
    (r"deklarierter User-Agent mit Kontakt verlangt", "declared user agent with contact required"), (r"Regierung Indien, öffentliche Listen", "Government of India, public lists"),
    (r"Datenbankrecht", "database right"), (r"amtliche Veröffentlichung", "official publication"), (r"öffentliche Excel-Listen", "public Excel lists"),
    (r"API-Key, Free-Tier limitiert; Daten-API separat \(siehe (.+?)\)", r"API key, free tier limited; data API separate (see \1)"),
    (r"Preview ohne Key \(max\. 500 Zeilen\), sonst API-Key", "preview without key (max. 500 rows), otherwise API key"),
    (r"US-Bundesdaten", "US federal data"), (r"API mit kostenloser Registrierung \(Key\)", "API with free registration (key)"),
    (r"POST \+ kostenloser Key", "POST + free key"), (r"offizielle REST-API \((\w+)\) nur mit beantragtem Zugang", r"official REST API (\1) only with requested access"),
    (r"ohne Key 1000 req/Tag", "without key 1000 req/day"), (r"Open-Data-CSV separat \(siehe (.+?)\)", r"open data CSV separate (see \1)"),
    (r"Bund CH", "Swiss Confederation"), (r"Alternative: ", "alternative: "),
    # API summary sentence (graph/api_summary.py)
    (r"(\d+) API-Hersteller mit aktivem US-DMF \((\d+) gesamt\)", r"\1 API makers with active US DMF (\2 total)"),
    (r"(\d+) bestätigte API-Hersteller aus EMA Annex IIA", r"\1 confirmed API makers from EMA Annex IIA"),
    (r"CEP: keine Daten", "CEP: no data"), (r"zugelassen in (\d+) Ländern", r"authorised in \1 countries"), (r" plus EU-zentral", " plus EU-central"),
    (r"\((\d+) Produkte, (\d+) MAHs\)", r"(\1 products, \2 MAHs)"), (r"(\d+) Batch-Release-Firmen aus (\d+) Leaflets", r"\1 batch-release companies from \2 leaflets"),
    (r"US-Substanzpatent bis ", "US substance patent until "), (r"US-Patente \(Formulierung/Verwendung\) bis ", "US patents (formulation/use) until "),
    (r"kein US-Patent auf Monopräparaten im Orange Book", "no US patent on single-agent products in the Orange Book"),
    (r"\(Patente auf Kombinationspräparaten bis ([\d-]+), separat geführt\)", r"(patents on combination products until \1, listed separately)"),
    (r" \(abgelaufen\)", " (expired)"), (r"EU-Patent/SPC: keine Daten", "EU patent/SPC: no data"),
    (r"(\d+) offene Engpassmeldungen \(EU zentral \+ ES\)", r"\1 open shortage notices (EU central + ES)"),
    (r"EU-DMF-Hinweis: noch keine Datengrundlage\.", "EU DMF hint: no data basis yet."),
]
_RULES = [(re.compile(p), r) for p, r in RULES]
GERMAN = re.compile(r"[äöüß]|\b(und|nicht|oder|mit|für|keine?|nur|aus|bis|wird|der|die|das)\b", re.I)


def en(text):
    if not isinstance(text, str) or not text:
        return text
    if text in EXACT:
        return EXACT[text]
    out = text
    for rx, rep in _RULES:
        out = rx.sub(rep, out)
    return out


def untranslated(texts):
    return sorted({t for t in texts if isinstance(t, str) and GERMAN.search(en(t))})
