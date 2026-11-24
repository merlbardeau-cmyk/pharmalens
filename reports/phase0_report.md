# PharmaLens – Phase 0 Quellenbericht
Stand: 2026-11-24 09:30 UTC · geprüft: 72 Quellen · 🟢 31 · 🟡 23 · 🔴 18 · nicht geprüft: 8
Rohspeicher: 71 Objekte, 23.2 MB, SHA-256 in `raw_object`. Lücken in `gap`: 26.

Ampel: 🟢 offizieller Download/API · 🟡 HTML erlaubt (Scraping nötig) · 🔴 nicht nutzbar (gesperrt, robots, WAF/CAPTCHA, Fehler).
Lizenz-Hinweise mit [zu verifizieren] sind Kenntnisstand, noch nicht gegen die Nutzungsbedingungen der Quelle geprüft.

## Wirkstoff-Stamm

| | Quelle | Land | HTTP | robots | Zugriff | Befund | Lizenz | Rhythmus |
|---|---|---|---|---|---|---|---|---|
| 🟢 | [ALT ChEMBL API (statt PubChem)](https://www.ebi.ac.uk/chembl/api/data/molecule/search.json?q=metformin&limit=1) | INT | 200 | allowed | api | API liefert application/json | CC BY-SA 3.0 [zu verifizieren] | quartalsweise |
| 🟢 | [DrugCentral](https://drugcentral.org/download) | INT | 200 | no_robots | download | Download-Seite mit 9 Datei-Links (csv, gz, txt, zip) | CC BY-SA 4.0 (DrugCentral-Projekt, UNM) [zu verifizieren] | jährlich |
| 🟢 | [FDA GSRS / UNII](https://gsrs.ncats.nih.gov/ginas/app/api/v1/substances/search?q=metformin&top=1) | US | 200 | no_robots | api | API liefert application/json | US-Bundesdaten, Public Domain | laufend |
| 🔴 | [EDQM Knowledge Database](https://extranet.edqm.eu/4DLink1/4DCGI/Web_View/mono/1) | EU | 200 | disallowed | none | HTTP 200, robots.txt verbietet den Pfad | EDQM/Europarat, Nutzung der Inhalte eingeschränkt [zu verifizieren] | laufend |
| 🔴 | [PubChem FTP Bulk](https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/) | INT | 200 | disallowed | none | HTTP 200, robots.txt verbietet den Pfad | NCBI, frei nutzbar | wöchentlich |
| 🔴 | [PubChem PUG-REST](https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/metformin/property/MolecularFormula,InChIKey/JSON) | INT | 200 | disallowed | none | HTTP 200, robots.txt verbietet den Pfad | NCBI, frei nutzbar; Limit max. 5 req/s | laufend |
| 🟡 | [WHO ATC/DDD Index](https://atcddd.fhi.no/atc_ddd_index/?code=A10BA02) | INT | 200 | no_robots | html | HTML zugänglich | Copyright WHO CC; systematische Kopie/Weiterverbreitung des Index nur mit Erlaubnis, vollständige Datei kostenpflichtig [zu verifizieren] | jährlich |

## API-Zertifikate & Werke

| | Quelle | Land | HTTP | robots | Zugriff | Befund | Lizenz | Rhythmus |
|---|---|---|---|---|---|---|---|---|
| 🟢 | [ALT FDA Data Dashboard API](https://api-datadashboard.fda.gov/v1/inspections_classifications) | US | 405 | no_robots | api | API erreichbar (Methode prüfen) | US-Bundesdaten; POST + kostenloser Key | wöchentlich |
| 🟢 | [FDA DMF-Liste](https://www.fda.gov/drugs/drug-master-files-dmfs/list-drug-master-files-dmfs) | US | 200 | allowed | download | Download-Seite mit 1 Datei-Links (download) | US-Bundesdaten, Public Domain | quartalsweise |
| 🟢 | [openFDA](https://api.fda.gov/download.json) | US | 200 | no_robots | api | API liefert application/json | openFDA, CC0/Public Domain; ohne Key 1000 req/Tag | wöchentlich |
| 🔴 | [CDSCO Written Confirmations](https://cdsco.gov.in/opencms/opencms/en/Home/) | IN | – | unreachable | none | nicht erreichbar: ConnectError: [Errno 104] Connection reset by peer | Regierung Indien, öffentliche Listen (PDF) [zu verifizieren] | unregelmässig |
| 🔴 | [EDQM CEP-Datenbank](https://extranet.edqm.eu/publications/recherches_CEP.shtml) | EU | 200 | disallowed | none | HTTP 200, robots.txt verbietet den Pfad | EDQM/Europarat [zu verifizieren] | täglich |
| 🔴 | [FDA Data Dashboard](https://datadashboard.fda.gov/oii/cd/inspections.htm) | US | 403 | no_robots | none | HTTP 403: Zugriff verweigert | US-Bundesdaten; API mit kostenloser Registrierung (Key) | wöchentlich |
| 🟡 | [EudraGMDP](https://eudragmdp.ema.europa.eu/inspections/gmpc/searchGMPCompliance.do) | EU | 200 | no_robots | html | HTML zugänglich | EMA, Reuse gemäss EMA Legal Notice mit Quellenangabe [zu verifizieren] | täglich |
| 🟡 | [FDA Import Alerts](https://www.accessdata.fda.gov/cms_ia/ialist.html) | US | 200 | allowed | html | HTML zugänglich | US-Bundesdaten, Public Domain | täglich |
| 🟡 | [FDA Warning Letters](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters) | US | 200 | allowed | html | HTML zugänglich | US-Bundesdaten, Public Domain | täglich |
| 🟡 | [WHO Prequalification APIs](https://extranet.who.int/prequal/medicines/prequalified/active-pharmaceutical-ingredients) | INT | 200 | allowed | html | HTML zugänglich | WHO [zu verifizieren] | laufend |

## Zulassungen EU zentral

| | Quelle | Land | HTTP | robots | Zugriff | Befund | Lizenz | Rhythmus |
|---|---|---|---|---|---|---|---|---|
| 🟢 | [EMA Article-57-Datenbank](https://www.ema.europa.eu/en/documents/other/article-57-product-data_en.xlsx) | EU | 200 | allowed | download | Direkter Download (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, 7,784,107 Bytes) | EMA, Reuse mit Quellenangabe erlaubt [zu verifizieren] | monatlich |
| 🟢 | [EMA Medicine data download](https://www.ema.europa.eu/en/documents/report/medicines-output-medicines-report_en.xlsx) | EU | 200 | allowed | download | Direkter Download (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, 907,869 Bytes) | EMA, Reuse mit Quellenangabe erlaubt [zu verifizieren] | täglich |
| 🟡 | [EU Union Product Database (Vet)](https://medicines.health.europa.eu/veterinary/en) | EU | 200 | no_robots | html | HTML zugänglich | EU-Kommission/EMA, Reuse gem. Commission Decision 2011/833/EU [zu verifizieren] | täglich |
| 🟡 | [HMA MRI Product Index](https://mri-production.cts-mrp.eu/) | EU | 200 | no_robots | html | HTML zugänglich – Seite JS-gerendert, Playwright nötig | HMA/CTS [zu verifizieren] | täglich |

## Nationale Register

| | Quelle | Land | HTTP | robots | Zugriff | Befund | Lizenz | Rhythmus |
|---|---|---|---|---|---|---|---|---|
| 🟢 | [ALT MA data.gov.ma Référentiel médicaments](https://data.gov.ma/data/fr/dataset/2cdfd9f4-289d-4e9a-8998-50bd03f8e874/resource/094733f5-5434-4163-b837-df0e7b665127/download/ref-des-medicaments-cnops-2014.xlsx) | MA | 200 | allowed | download | Direkter Download (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, 530,243 Bytes) | ODbL; Stand 2014 (CNOPS) – veraltet | einmalig |
| 🟢 | [ALT TR SGK Erstattungsliste EK-4/A](https://www.sgk.gov.tr/Download/DownloadFile?f=f5e92901-9e16-424b-9d18-4143128e8c63.xlsx&d=24d41336-97c0-4198-b21d-67bb3b7dc272) | TR | 200 | no_robots | download | Direkter Download (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, 140,556 Bytes) | SGK, amtliche Veröffentlichung [zu verifizieren] | wöchentlich |
| 🟢 | [CH Swissmedic Listen](https://www.swissmedic.ch/swissmedic/de/home/services/listen_neu.html) | CH | 200 | no_robots | download | Download-Seite mit 44 Datei-Links (xlsx) | Swissmedic, öffentliche Excel-Listen [zu verifizieren] | monatlich |
| 🟢 | [ES AEMPS CIMA REST](https://cima.aemps.es/cima/rest/medicamentos?nombre=metformina&pagina=1) | ES | 200 | allowed | api | API liefert application/json | AEMPS, Reuse erlaubt mit Quellenangabe [zu verifizieren] | täglich |
| 🟢 | [FR BDPM](https://base-donnees-publique.medicaments.gouv.fr/telechargement) | FR | 200 | allowed | download | Download-Seite mit 11 Datei-Links (txt) | Licence Ouverte / Etalab [zu verifizieren] | monatlich |
| 🟢 | [IT AIFA Open Data](https://www.aifa.gov.it/liste-farmaci-a-h) | IT | 200 | unreachable | download | Download-Seite mit 4 Datei-Links (csv) | AIFA Open Data, IODL/CC-BY [zu verifizieren] | monatlich |
| 🟢 | [US DailyMed](https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?drug_name=metformin&pagesize=1) | US | 200 | no_robots | api | API liefert application/json | NLM, frei nutzbar | täglich |
| 🟢 | [US Drugs@FDA](https://www.fda.gov/media/89850/download) | US | 200 | allowed | download | Direkter Download (application/zip, 6,120,928 Bytes) | US-Bundesdaten, Public Domain | wöchentlich |
| 🔴 | [ALT DE BfArM AMIce Portal](https://portal.bfarm.de/amguifree/?accessid=pharmnet_amis_off_ppv) | DE | 200 | no_robots | none | HTTP 200, technisch erreichbar, aber: Authentifizierungs-Weiterleitung (SSO) – Login wird nicht verwendet | BfArM | wöchentlich |
| 🔴 | [ALT DE Gebrauchsinformation 4.0](https://gebrauchsinformation4-0.de/rechtliche-hinweise) | DE | 200 | allowed | none | HTTP 200, technisch erreichbar, aber: Nutzungsbedingungen: Datenbanken urheberrechtlich geschützt, Vervielfältigung nur mit schriftlicher Genehmigung – Lizenz nötig | Rote Liste Service GmbH; Datenbankrecht | täglich |
| 🔴 | [DE BfArM AMIce (frei)](https://auth.bfarm.de/sso-home/amguifree) | DE | – | disallowed | none | robots.txt auf auth.bfarm.de verbietet alles (Disallow: /); Weiterleitung auf portal.bfarm.de/amguifree – Host nicht freigegeben, robots dort ungeprüft | BfArM AMIce, freie Recherche [zu verifizieren] | wöchentlich |
| 🔴 | [MA DMP Marokko](https://dmp.sante.gov.ma/) | MA | – | unreachable | none | nicht erreichbar: ConnectError: [Errno 104] Connection reset by peer | [zu verifizieren] | unbekannt |
| 🔴 | [TN DPM Tunesien](https://www.dpm.tn/) | TN | – | unreachable | none | nicht erreichbar: ConnectError: [Errno 104] Connection reset by peer | [zu verifizieren] | unbekannt |
| 🔴 | [TR TİTCK](https://www.titck.gov.tr/dinamikmodul/43) | TR | 500 | no_robots | none | HTTP 500, Web Application Firewall blockiert Cloud-IP/Bot – wird nicht umgangen | TİTCK [zu verifizieren] | monatlich |
| 🟡 | [AT BASG Arzneispezialitätenregister](https://medikamente.basg.gv.at/de/medicinal-products/) | AT | 200 | no_robots | html | HTML zugänglich – Seite JS-gerendert, Playwright nötig | BASG [zu verifizieren] | wöchentlich |
| 🟡 | [CH AIPS swissmedicinfo](https://www.swissmedicinfo.ch/) | CH | 200 | no_robots | html | HTML zugänglich | AIPS; Download nur nach Akzeptanz der Nutzungsbedingungen [zu verifizieren] | wöchentlich |
| 🟡 | [DE BfArM PharmNet.Bund (AMIce)](https://www.pharmnet-bund.de/PharmNet/DE/Oeffentlichkeit/Arzneimittel-Informationssystem/_node.html) | DE | 200 | no_robots | html | HTML zugänglich | BfArM; eigentliche AMIce-Recherche läuft über auth.bfarm.de/sso-home/amguifree (Proxy blockiert trotz Freigabe) [zu verifizieren] | wöchentlich |
| 🟡 | [DK DKMA](https://laegemiddelstyrelsen.dk/da/) | DK | 200 | no_robots | html | HTML zugänglich | DKMA [zu verifizieren]; Produktresuméer separat (siehe DK produktresume.dk) | wöchentlich |
| 🟡 | [DK produktresume.dk](https://www.produktresume.dk/AppBuilder/search) | DK | 200 | no_robots | html | HTML zugänglich – Seite JS-gerendert, Playwright nötig | DKMA [zu verifizieren] | wöchentlich |
| 🟡 | [IT AIFA Banca Dati Farmaci](https://medicinali.aifa.gov.it/it/) | IT | 200 | no_robots | html | HTML zugänglich | AIFA [zu verifizieren]; Open-Data-CSV separat (siehe IT AIFA Open Data) | wöchentlich |
| 🟡 | [NL CBG Geneesmiddeleninformatiebank](https://www.geneesmiddeleninformatiebank.nl/ords/f?p=111:1:0::NO:RP,1:P0_DOMAIN,P0_LANG:H,NL) | NL | 200 | allowed | html | HTML zugänglich | CBG-MEB [zu verifizieren] | wöchentlich |
| 🟡 | [SE FASS](https://fass.se/LIF/startpage) | SE | 200 | allowed | html | HTML zugänglich | LIF/FASS: Inhalte urheberrechtlich geschützt, systematisches Kopieren untersagt [zu verifizieren]; Alternative: Läkemedelsverket NPL | wöchentlich |
| 🟡 | [SE Läkemedelsverket](https://www.lakemedelsverket.se/sv) | SE | 200 | allowed | html | HTML zugänglich | Läkemedelsverket; NPL-Download-Pfad noch nicht lokalisiert [zu verifizieren] | wöchentlich |
| 🟡 | [UK MHRA Products](https://products.mhra.gov.uk/search/?search=metformin&page=1) | GB | 200 | allowed | html | HTML zugänglich | Crown Copyright, Open Government Licence v3.0 [zu verifizieren] | wöchentlich |

## Patente & SPC

| | Quelle | Land | HTTP | robots | Zugriff | Befund | Lizenz | Rhythmus |
|---|---|---|---|---|---|---|---|---|
| 🟢 | [ALT EPO OPS Register-Service (statt Register-Web)](https://ops.epo.org/3.2/rest-services/register/publication/epodoc/EP1000000/biblio) | EP | 403 | no_robots | api | HTTP 403: API erreichbar, Zugang erfordert (kostenlosen) Key/Registrierung | EPO OPS Fair-Use; kostenloser OAuth-Key | monatlich |
| 🟢 | [EPO OPS](https://ops.epo.org/3.2/rest-services/published-data/search?q=ti%3Dmetformin) | EP | 403 | no_robots | api | HTTP 403: API erreichbar, Zugang erfordert (kostenlosen) Key/Registrierung | EPO OPS Fair-Use; kostenlose Registrierung (OAuth Key), 4 GB/Woche frei | wöchentlich |
| 🟢 | [US Orange Book](https://www.fda.gov/media/76860/download) | US | 200 | allowed | download | Direkter Download (application/zip, 1,104,034 Bytes) | US-Bundesdaten, Public Domain | monatlich |
| 🔴 | [European Patent Register](https://register.epo.org/application?number=EP00916888&tab=main) | EP | 403 | no_robots | none | HTTP 403, CAPTCHA/Bot-Challenge erkannt – wird nicht umgangen | EPO; automatisierte Abfrage nur über OPS-Register-Service [zu verifizieren] | monatlich |
| 🟡 | [DE DPMAregister (SPC)](https://register.dpma.de/DPMAregister/Uebersicht) | DE | 200 | allowed | html | HTML zugänglich | DPMA; automatisierte Abfrage eingeschränkt, DPMAconnect kostenpflichtig [zu verifizieren] | monatlich |
| 🟡 | [UK IPO Ipsum (SPC)](https://www.ipo.gov.uk/p-ipsum.htm) | GB | 200 | no_robots | html | HTML zugänglich | Crown Copyright [zu verifizieren] | monatlich |

## Engpässe

| | Quelle | Land | HTTP | robots | Zugriff | Befund | Lizenz | Rhythmus |
|---|---|---|---|---|---|---|---|---|
| 🟢 | [EMA Shortages (ESMP)](https://www.ema.europa.eu/en/documents/report/medicines-output-shortages-report_en.xlsx) | EU | 200 | allowed | download | Direkter Download (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, 88,235 Bytes) | EMA [zu verifizieren] | täglich |
| 🟢 | [ES AEMPS CIMA Engpässe](https://cima.aemps.es/cima/rest/psuministro?pagina=1) | ES | 200 | allowed | api | API liefert application/json | AEMPS [zu verifizieren] | täglich |
| 🟡 | [CH BWL Meldestelle Heilmittel](https://www.bwl.admin.ch/de/meldestelle-heilmittel) | CH | 200 | allowed | html | HTML zugänglich | Bund CH, OGD-Bedingungen [zu verifizieren] | wöchentlich |
| 🟡 | [DE BfArM Lieferengpässe](https://www.bfarm.de/DE/Arzneimittel/Arzneimittelinformationen/Lieferengpaesse/_node.html) | DE | 200 | no_robots | html | HTML zugänglich | BfArM; Datenbank selbst auf anwendungen.pharmnet-bund.de (Host nicht freigegeben) | täglich |
| 🟡 | [FR ANSM Ruptures](https://ansm.sante.fr/disponibilites-des-produits-de-sante/medicaments) | FR | 200 | allowed | html | HTML zugänglich | ANSM [zu verifizieren] | täglich |

## Ausschreibungen

| | Quelle | Land | HTTP | robots | Zugriff | Befund | Lizenz | Rhythmus |
|---|---|---|---|---|---|---|---|---|
| 🟢 | [TED API v3](https://api.ted.europa.eu/v3/notices/search) | EU | 200 | no_robots | api | API liefert application/json | EU-Amt für Veröffentlichungen, Reuse erlaubt (2011/833/EU) | täglich |

## Volumen & Handel

| | Quelle | Land | HTTP | robots | Zugriff | Befund | Lizenz | Rhythmus |
|---|---|---|---|---|---|---|---|---|
| 🟢 | [ALT NHSBSA EPD Bulk-CSV (statt OpenPrescribing)](https://opendata.nhsbsa.net/dataset/english-prescribing-data-epd) | GB | 200 | allowed | download | Download-Seite mit 138 Datei-Links (csv, zip) | Open Government Licence v3.0 [zu verifizieren] | monatlich |
| 🟢 | [Eurostat Comext](https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/dataflow/ESTAT/DS-045409/latest) | EU | 200 | allowed | api | API liefert application/vnd.sdmx.structure+xml | Eurostat, Reuse erlaubt mit Quellenangabe | monatlich |
| 🟢 | [Medicaid SDUD](https://data.medicaid.gov/api/1/metastore/schemas/dataset/items?show-reference-ids=false) | US | 200 | no_robots | api | API liefert application/json | CMS, Public Domain | quartalsweise |
| 🟢 | [UN Comtrade API (public preview)](https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode=756&period=2023&cmdCode=300490) | INT | 200 | no_robots | api | API liefert application/json | UN Comtrade; Preview ohne Key (max. 500 Zeilen), sonst API-Key | monatlich |
| 🔴 | [NHSBSA Open Data Portal](https://opendata.nhsbsa.net/api/3/action/package_list) | GB | 200 | disallowed | none | HTTP 200, robots.txt verbietet den Pfad | Open Government Licence v3.0 [zu verifizieren] | monatlich |
| 🔴 | [OpenPrescribing (NHS England)](https://openprescribing.net/api/1.0/bnf_code/?q=metformin&format=json) | GB | 403 | allowed | none | HTTP 403, CAPTCHA/Bot-Challenge erkannt – wird nicht umgangen | Bennett Institute; Daten NHSBSA unter OGL [zu verifizieren] | monatlich |
| 🟡 | [UN Comtrade](https://comtrade.un.org/) | INT | 200 | allowed | html | API-Endpunkt liefert text/html statt JSON/XML | UN Comtrade; API-Key, Free-Tier limitiert; Daten-API separat (siehe UN Comtrade API) | monatlich |

## Firmenstruktur

| | Quelle | Land | HTTP | robots | Zugriff | Befund | Lizenz | Rhythmus |
|---|---|---|---|---|---|---|---|---|
| 🟢 | [ALT CH UID-Register Public Services](https://www.uid-wse.admin.ch/V5.0/PublicServices.svc?wsdl) | CH | 200 | no_robots | api | API liefert text/xml | BFS UID-Register, öffentliche Daten, frei; Rate-Limit beachten [zu verifizieren] | täglich |
| 🟢 | [ALT Wikidata EntityData (statt SPARQL)](https://www.wikidata.org/wiki/Special:EntityData/Q215212.json) | INT | 200 | allowed | api | API liefert application/json | CC0 | laufend |
| 🟢 | [GLEIF LEI API](https://api.gleif.org/api/v1/lei-records?filter%5Bentity.legalName%5D=Sandoz%20AG&page%5Bsize%5D=1) | INT | 200 | allowed | api | API liefert application/vnd.api+json | CC0 | täglich |
| 🟢 | [SEC EDGAR Full-Text Search](https://efts.sec.gov/LATEST/search-index?q=%22subsidiaries%22&forms=10-K) | US | 200 | no_robots | api | API liefert application/json | Public Domain; SEC verlangt deklarierten User-Agent mit Kontakt, max. 10 req/s | quartalsweise |
| 🟢 | [SEC EDGAR submissions API](https://data.sec.gov/submissions/CIK0000078003.json) | US | 200 | no_robots | api | API liefert application/json | Public Domain; deklarierter User-Agent mit Kontakt verlangt | täglich |
| 🔴 | [CH Zefix](https://www.zefix.ch/en/search/entity/welcome) | CH | 500 | no_robots | none | HTTP 500, Web Application Firewall blockiert Cloud-IP/Bot – wird nicht umgangen | Zefix; offizielle REST-API (ZefixPublicREST) nur mit beantragtem Zugang | täglich |
| 🔴 | [Wikidata Dumps](https://dumps.wikimedia.org/wikidatawiki/entities/) | INT | – | unreachable | none | nicht erreichbar: ConnectError: [Errno 104] Connection reset by peer | CC0 | wöchentlich |
| 🔴 | [Wikidata SPARQL](https://query.wikidata.org/sparql?query=ASK%7B%7D&format=json) | INT | 200 | disallowed | none | HTTP 200, robots.txt verbietet den Pfad | CC0 | laufend |

## Nicht geprüft (Host fehlt oder Quelle unbekannt)

| Quelle | Land | Host | Grund |
|---|---|---|---|
| DE BfArM Engpass-Datenbank | DE | anwendungen.pharmnet-bund.de | Host nicht freigegeben |
| NHWSTAT Nordics | NO | www.norpd.no / statistik | Host nicht freigegeben, URL in Brief fehlt |
| medstat.dk | DK | medstat.dk | Host nicht freigegeben |
| INPI SPC | FR | data.inpi.fr | Host nicht freigegeben, URL in Brief fehlt |
| Irish Patent Office | IE | eregister.ipoi.gov.ie | Host nicht freigegeben, URL in Brief fehlt |
| DE Unternehmensregister | DE | www.unternehmensregister.de | Host nicht freigegeben |
| FR Infogreffe / RNE | FR | data.inpi.fr / www.infogreffe.fr | Host nicht freigegeben |
| Algerien Register | DZ | unbekannt | Keine offizielle Online-Quelle im Brief; Behörde (ANPP) zu identifizieren |
