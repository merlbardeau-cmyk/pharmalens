"""Country detection for manufacturer addresses.

Never derive ISO codes by slicing strings ("GE" for Germany is Georgia). Only exact country
names (multilingual) or explicit postal prefixes (D-12345) are accepted; otherwise None.
"""
from __future__ import annotations

import re

from models.db import norm_text

_NAMES = {
    "DE": ["germany", "deutschland", "alemania", "allemagne", "germania", "duitsland", "tyskland", "almanya"],
    "FR": ["france", "francia", "frankreich", "frankrijk", "frankrike", "fransa"],
    "ES": ["spain", "espana", "espagne", "spanien", "spagna", "spanje"],
    "IT": ["italy", "italia", "italie", "italien", "italie"],
    "PT": ["portugal", "portogallo"],
    "NL": ["netherlands", "the netherlands", "paises bajos", "holanda", "pays-bas", "pays bas", "niederlande", "paesi bassi", "nederland"],
    "BE": ["belgium", "belgica", "belgique", "belgien", "belgio", "belgie"],
    "IE": ["ireland", "irlanda", "irlande", "irland"],
    "GB": ["united kingdom", "uk", "reino unido", "royaume-uni", "royaume uni", "vereinigtes konigreich", "regno unito", "great britain"],
    "AT": ["austria", "autriche", "osterreich"],
    "CH": ["switzerland", "suiza", "suisse", "schweiz", "svizzera"],
    "PL": ["poland", "polonia", "pologne", "polen"],
    "HU": ["hungary", "hungria", "hongrie", "ungarn", "ungheria"],
    "CZ": ["czech republic", "czechia", "republica checa", "republique tcheque", "tschechien", "tschechische republik", "repubblica ceca"],
    "SK": ["slovakia", "eslovaquia", "slovaquie", "slowakei", "slovacchia"],
    "SI": ["slovenia", "eslovenia", "slovenie", "slowenien"],
    "MK": ["north macedonia", "macedonia del norte", "macedoine du nord"],
    "RS": ["serbia", "serbie", "serbien"],
    "BA": ["bosnia and herzegovina", "bosnie-herzegovine"],
    "HR": ["croatia", "croacia", "croatie", "kroatien", "croazia"],
    "GR": ["greece", "grecia", "grece", "griechenland"],
    "CY": ["cyprus", "chipre", "chypre", "zypern", "cipro"],
    "MT": ["malta", "malte"],
    "RO": ["romania", "rumania", "roumanie", "rumanien"],
    "BG": ["bulgaria", "bulgarie", "bulgarien"],
    "SE": ["sweden", "suecia", "suede", "schweden", "svezia", "sverige"],
    "DK": ["denmark", "dinamarca", "danemark", "danemark", "danimarca", "danmark"],
    "FI": ["finland", "finlandia", "finlande", "finnland"],
    "NO": ["norway", "noruega", "norvege", "norwegen", "norvegia"],
    "IS": ["iceland", "islandia", "islande", "island"],
    "LV": ["latvia", "letonia", "lettonie", "lettland"],
    "LT": ["lithuania", "lituania", "lituanie", "litauen"],
    "EE": ["estonia", "estonie", "estland"],
    "LU": ["luxembourg", "luxemburgo", "luxemburg", "lussemburgo"],
    "IN": ["india", "inde", "indien"],
    "CN": ["china", "chine", "cina"],
    "IL": ["israel"],
    "TR": ["turkey", "turquia", "turquie", "turkei", "turkiye"],
    "US": ["usa", "united states", "united states of america", "estados unidos", "etats-unis", "etats unis", "vereinigte staaten"],
    "JP": ["japan", "japon", "giappone"],
    "KR": ["korea", "south korea", "republic of korea", "corea del sur", "coree du sud"],
}
NAME_TO_ISO = {n: iso for iso, names in _NAMES.items() for n in names}
POSTAL_PREFIX = {"D": "DE", "F": "FR", "E": "ES", "I": "IT", "A": "AT", "CH": "CH", "NL": "NL", "B": "BE",
                 "P": "PT", "IRL": "IE", "PL": "PL", "DK": "DK", "S": "SE", "FIN": "FI", "H": "HU", "CZ": "CZ", "SLO": "SI"}
_POSTAL_RX = re.compile(r"\b(D|F|E|I|A|CH|NL|B|P|IRL|PL|DK|S|FIN|H|CZ|SLO)[-–]\s?\d{3,5}\b")


def country_of(lines: list[str]) -> tuple[str | None, str]:
    """returns (iso2, basis). Checks lines bottom-up for an exact country name, then postal prefixes."""
    for line in reversed(lines):
        t = norm_text(line).strip(" .,;:()")
        t = re.sub(r"^(republique|republica|republic|repubblica|republik) (de |of |di |del )?(la )?", "", t)
        if t in NAME_TO_ISO:
            return NAME_TO_ISO[t], f"country name '{line.strip()}'"
        for part in re.findall(r"\(([^)]+)\)", norm_text(line)):  # "... Madrid (ESPAÑA)"
            if part.strip() in NAME_TO_ISO:
                return NAME_TO_ISO[part.strip()], f"country name in '{line.strip()}'"
        last = re.split(r"[,\-–]\s*", t)[-1].strip(" .")
        if last in NAME_TO_ISO and len(last) > 3:
            return NAME_TO_ISO[last], f"country name in '{line.strip()}'"
        words = t.split()
        for k in (3, 2, 1):  # "Paola PLA 3000 Malta"
            tail = " ".join(words[-k:])
            if len(words) > k and tail in NAME_TO_ISO and len(tail) > 3:
                return NAME_TO_ISO[tail], f"country name at end of '{line.strip()}'"
    for line in lines:
        m = _POSTAL_RX.search(line)
        if m:
            return POSTAL_PREFIX[m.group(1)], f"postal prefix '{m.group(0)}'"
    return None, "not determinable"
