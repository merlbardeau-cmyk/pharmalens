import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from enrich.leaflet_parser import parse  # noqa: E402
from models.countries import country_of  # noqa: E402

ES = ["Titular de la autorización de comercialización y responsable de la fabricación", "Titular de la autorización de comercialización",
      "Merck Santé s.a.s.", "37 Rue Saint Romain", "F-69008 Lyon", "Francia", "Responsable de la fabricación",
      "Merck Santé s.a.s.", "2 rue du Pressoir Vert", "45400 Semoy", "Francia", "o", "Merck, S.L.", "Polígono Merck",
      "08100 Mollet del Vallés", "(Barcelona)", "España", "o (sólo para Grecia)", "Merck KGaA", "Frankfurter Str. 250",
      "64293 Darmstadt", "Alemania", "Fecha de la última revisión de este prospecto: 01/2025"]

FR = ["Titulaire de l’autorisation de mise sur le marché", "ACCORD HEALTHCARE FRANCE SAS", "Exploitant de l’autorisation",
      "ACCORD", "Fabricant", "LABORATORI FUNDACIÓ DAU", "C/ C, 12-14 Pol. Ind. Zona Franca", "Barcelona 08040", "ESPAGNE",
      "Ou", "Accord Healthcare Polska Sp. z.o.o.", "Ul. Lutomierska 50", "Pabianice 95-200", "POLOGNE",
      "Noms du médicament dans les Etats membres"]


def test_es_three_sites_with_countries():
    s = parse(ES)
    assert [x["company"] for x in s] == ["Merck Santé s.a.s.", "Merck, S.L.", "Merck KGaA"]
    assert [x["country"] for x in s] == ["FR", "ES", "DE"]
    assert "Responsable de la fabricación" in s[0]["quote"] and "45400 Semoy" in s[0]["quote"]


def test_fr_sites():
    s = parse(FR)
    assert [(x["company"], x["country"]) for x in s] == [("LABORATORI FUNDACIÓ DAU", "ES"), ("Accord Healthcare Polska Sp. z.o.o.", "PL")]


def test_germany_is_never_georgia():
    assert country_of(["Hexal AG", "Industriestr. 25", "83607 Holzkirchen", "Germany"])[0] == "DE"
    assert country_of(["Hexal AG", "D-83607 Holzkirchen"])[0] == "DE"
    assert country_of(["Some Co", "Tbilisi", "GE"])[0] is None  # bare 2-letter codes are not trusted


def test_no_heading_returns_empty():
    assert parse(["Composición", "Cada comprimido contiene 850 mg"]) == []


def test_sites_without_separator_are_split_at_country_line():
    lines = ["Responsable de la fabricación", "Lek d.d, PE PROIZVODNJA LENDAVA", "Trimlini 2D", "Lendava, 9220", "Eslovenia",
             "Novartis Farmacéutica, S.A.", "Gran Via de les Corts Catalanes, 764", "08013 Barcelona", "España",
             "Novartis Pharma GmbH", "Sophie-Germain-Strasse 10", "90443 Nürnberg", "Alemania",
             "Fecha de la última revisión de este prospecto: 03/2024"]
    s = parse(lines)
    assert [(x["company"], x["country"]) for x in s] == [
        ("Lek d.d, PE PROIZVODNJA LENDAVA", "SI"), ("Novartis Farmacéutica, S.A.", "ES"), ("Novartis Pharma GmbH", "DE")]


def test_annex_iia_stops_at_split_heading_and_skips_form_headers():
    lines = ["Name and address of the manufacturer(s) responsible for batch release", "Film-coated tablets",
             "Novartis Farma S.p.A", "Via Provinciale Schito 131", "80058 Torre Annunziata (NA)", "Italy", "or",
             "Granules in capsules for opening", "Novartis Pharma GmbH", "Roonstraße 25", "90429 Nuremberg", "Germany", "or",
             "The printed package leaflet of the medicinal product must state the name and address", "or", "B.",
             "CONDITIONS OR RESTRICTIONS REGARDING SUPPLY AND USE", "Medicinal product subject to medical prescription."]
    s = parse(lines)
    assert [(x["company"], x["country"]) for x in s] == [("Novartis Farma S.p.A", "IT"), ("Novartis Pharma GmbH", "DE")]


def test_es_contact_lines_and_split_stop_heading():
    lines = ["Responsable de la fabricación", "Tel.: +357 25553000", "info@remedica.com.cy", "ó", "Pharmadox Healthcare Ltd.",
             "KW20A Kordin Industrial Park", "Paola PLA 3000 Malta", "Fecha de la", "última", "revisión de", "este prospecto: julio 2025"]
    s = parse(lines)
    assert [(x["company"], x["country"]) for x in s] == [("Pharmadox Healthcare Ltd.", "MT")]
    assert "@" not in s[0]["quote"]


def test_inline_country_variants():
    assert country_of(["LABORATORIOS NORMON, S.A.", "Ronda de Valdecarrizo, 6 – 28760 Tres Cantos – Madrid (ESPAÑA)"])[0] == "ES"
    assert country_of(["ALKALOID-INT D.O.O.", "1231 LJUBLJANA", "republique de slovenie"])[0] == "SI"


def test_junk_blocks_rejected():
    assert parse(["Fabricant", "N", "A,", "E", "S", "P", "A", "G", "N", "E"]) == []
    assert parse(["Responsable de la fabricación", "Este medicamento", "está autorizado en los estados miembros"]) == []


def test_line_ending_with_country_closes_site_but_not_company_line():
    lines = ["Responsable de la fabricación", "LABORATORI FUNDACIÓ DAU", "C/ C, 12-14 Pol. Ind. Zona Franca, Barcelona,",
             "08040 Barcelona, España", "Synoptis Industrial Sp. z o.o.", "ul. Rabowicka 15", "62-020 Swarzedz", "Polonia",
             "Boehringer Ingelheim France", "100-104 avenue de France", "75013 Paris", "Francia"]
    s = parse(lines)
    assert [(x["company"], x["country"]) for x in s] == [
        ("LABORATORI FUNDACIÓ DAU", "ES"), ("Synoptis Industrial Sp. z o.o.", "PL"), ("Boehringer Ingelheim France", "FR")]


def test_nl_leaflet():
    lines = ["Houder van de vergunning voor het in de handel brengen en fabrikant", "Registratiehouder:", "Mylan Pharmaceuticals Ltd",
             "Damastown Industrial Park", "Dublin 15", "Ierland", "Voor informatie en inlichtingen:", "Mylan B.V.", "Krijgsman 20",
             "Fabrikant:", "Mylan Hungary Kft,", "H-2900 Komárom, Mylan út. 1, Hongarije", "Logiters, Logistica, Portugal, S.A.",
             "Estrada dos Arneiros, 4, Azambuja, 2050-306, Portugal", "In het register ingeschreven onder", "RVG 104243"]
    s = parse(lines)
    assert [(x["company"], x["country"]) for x in s] == [("Mylan Hungary Kft,", "HU"), ("Logiters, Logistica, Portugal, S.A.", "PT")]


def test_nl_single_line_sites_street_first_and_noise():
    lines = ["Fabrikant", "KRKA, d.d., Novo mesto, Šmarješka cesta 6, 8501 Novo mesto, Slovenië",
             "TAD Pharma GmbH, Heinz-Lohmann-Straße 5, 27472 Cuxhaven, Duitsland", "Dit geneesmiddel is ingeschreven"]
    s = parse(lines)
    assert [(x["company"], x["country"]) for x in s] == [("KRKA, d.d.", "SI"), ("TAD Pharma GmbH", "DE")]
    assert parse(["Fabrikant", "Swensweg 5", "2031 GA Haarlem", "Nederland"]) == []
    assert parse(["Fabrikant", "Module 1", "Administrative information", "and prescribing information"]) == []
    assert [x["company"] for x in parse(["Fabrikant: Pharmachemie B.V.", "Swensweg 5", "2031 GA Haarlem", "Nederland"])] == ["Pharmachemie B.V."]


def test_at_combined_vet_and_two_comma_lines():
    s = parse(["Pharmazeutischer Unternehmer und Hersteller", "IBSA Farmaceutici Italia Srl", "Via Martiri di Cefalonia 2",
               "26900 Lodi", "Italien", "Syntroxine 13 Mikrogramm Weichkapseln– Z. Nr.: 1-30382"])
    assert [(x["company"], x["country"]) for x in s] == [("IBSA Farmaceutici Italia Srl", "IT")]
    s = parse(["Pharmazeutischer Unternehmer und Hersteller", "Pharmazeutischer Unternehmer:", "Sandoz GmbH, 6250 Kundl, Österreich",
               "Hersteller:", "Lek Pharmaceuticals d.d., 1526 Laibach, Slowenien", "Z.Nr.: 143060"])
    assert [(x["company"], x["country"]) for x in s] == [("Lek Pharmaceuticals d.d.", "SI")]
    s = parse(["Für die Chargenfreigabe verantwortlicher Hersteller:", "Ceva Santé Animale", "Boulevard de la Communication",
               "53950 Louverné", "Frankreich", "Örtlicher Vertreter"])
    assert [(x["company"], x["country"]) for x in s] == [("Ceva Santé Animale", "FR")]


def test_sites_without_country_are_rejected():
    assert parse(["Fabrikant", "RVG100984", "RVG100986", "RVG100987"]) == []
    assert parse(["Fremstiller", "Danmark: Metformin Sandoz", "Findland: Oramet 500 mg"]) == []
    s = parse(["Fabrikant", "Pharmachemie B.V.", "Swensweg 5", "2031 GA Haarlem"], home_country="NL")
    assert [(x["company"], x["country"]) for x in s] == [("Pharmachemie B.V.", "NL")]
    assert parse(["Hersteller:", "Balkanpharma – Dupnitsa AD", "3 Samokovsko Shoose Str.", "2600 Dupnitsa"], home_country="AT") == []


def test_member_state_name_lists_end_section():
    s = parse(["Fremstiller", "Laboratori Fundacio DAU", "C/ C, 12-14", "08040 Barcelona", "Spanien",
               "Dette lægemiddel er godkendt i EØS under følgende navne", "Tyskland: Atorvastatin Amarox"])
    assert [(x["company"], x["country"]) for x in s] == [("Laboratori Fundacio DAU", "ES")]
    assert parse(["Fremstiller", "Tyskland: Atorvastatin Amarox", "Spanien: Atorvastatina Amarox"]) == []


def test_sentences_are_not_companies():
    assert parse(["Fabrikant", "Dit medicijn is geregistreerd in lidstaten van de Europese Economische Ruimte onder de volgende namen:",
                  "Nederland", "Duitsland"]) == []


def test_company_cut_after_legal_form():
    s = parse(["Hersteller:", "STADA Arzneimittel AG, Stadastraße 2 - 18, 61118 Bad Vilbel", "Deutschland"])
    assert [(x["company"], x["country"]) for x in s] == [("STADA Arzneimittel AG", "DE")]
    s = parse(["Hersteller:", "Clonmel Healthcare Ltd., Waterford Road, Co. Tipperary, Clonmel, Irland", "Z.Nr.: 1"])
    assert [(x["company"], x["country"]) for x in s] == [("Clonmel Healthcare Ltd.", "IE")]
