"""Generic parser for the manufacturer / batch-release section of a leaflet (PL) or Annex IIA.

Input: plain text lines of the document. Output: list of sites with verbatim quote.
Never guesses: if the heading is not found, returns [] and the caller writes a gap.
"""
from __future__ import annotations

import html
import re

from models.countries import NAME_TO_ISO, country_of
from models.db import norm_text

START = [
    re.compile(r"^(Responsable de la fabricaci[oó]n|Fabricante)\s*:?$", re.I),            # ES
    re.compile(r"^Fabricant(s)?\s*:?$", re.I),                                               # FR
    re.compile(r"^Name and address of the manufacturer\(?s?\)? responsible for batch release\s*:?$", re.I),  # EMA IIA
    re.compile(r"^Manufacturer\(?s?\)?\s*:?$", re.I),                                         # EN PL
    re.compile(r"^Hersteller(in)?\s*:?$", re.I),                                             # DE/CH
]
COMBINED = re.compile(r"^Titular de la autorizaci[oó]n de comercializaci[oó]n y responsable de la fabricaci[oó]n\s*:?$", re.I)
STOP = re.compile(
    r"^(Pueden solicitar|Representante local|Fecha de la [uú]ltima revisi[oó]n|Este medicamento est[aá] autorizado|"
    r"La informaci[oó]n detallada|Otras fuentes|Puede solicitar|Fecha de la|Este prospecto|Fecha de [uú]ltima|"
    r"Noms du m[ée]dicament|Ce m[ée]dicament est autoris|La derni[eè]re date|Date d.approbation|Autres sources|"
    r"Repr[ée]sentant|Pour toute information|Conformément à la réglementation|"
    r"B\.$|C\.$|B\. CONDITIONS|B\.\s+CONDITIONS|CONDITIONS OR RESTRICTIONS|The printed package leaflet|Name and address of the manufacturer.* biological|C\. OTHER CONDITIONS|"
    r"This leaflet was last revised|For any information|Marketing Authorisation Holder|"
    r"Titular de la autorizaci[oó]n|Titulaire de l.autorisation|Exploitant)", re.I)
FORM_HEADER = re.compile(r"^(film-coated |prolonged-release |gastro-resistant |hard |soft |orodispersible )?"
                         r"(tablets?|capsules?|granules|powder|solution|suspension|injection|concentrate|pens?|syringes?|"
                         r"solution for injection.*|granules in capsules.*|oral .*)\b.{0,60}$", re.I)
CONTACT = re.compile(r"@|\b(tel|t[eé]l[eé]phone|tfno|phone|fax|e-?mail|correo)\b\.?\s*:?|https?://|www\.", re.I)
SEP = re.compile(r"^(o|ó|ou|or|oder|y|et|and)(\s*\(.{0,80}\))?\s*:?$", re.I)
MAX_LINES = 120


def html_to_lines(text: str) -> list[str]:
    text = re.sub(r"<(script|style).*?</\1>", "", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", text))
    return [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln.strip() and ln.strip() != "\xa0"]


def find_section(lines: list[str]) -> tuple[int, str] | None:
    for rx in START:
        for i, ln in enumerate(lines):
            if rx.match(ln):
                return i, ln
    for i, ln in enumerate(lines):
        if COMBINED.match(ln):
            return i, ln
    return None


def parse(lines: list[str], home_country: str | None = None) -> list[dict]:
    hit = find_section(lines)
    if hit is None:
        return []
    start, heading = hit
    body = []
    for ln in lines[start + 1:start + 1 + MAX_LINES]:
        if STOP.match(ln):
            break
        if CONTACT.search(ln):
            continue  # no contact data (GDPR rule) and never a company line
        body.append(ln)
    blocks, cur = [], []
    for ln in body:
        if SEP.match(ln):
            if cur:
                blocks.append(cur)
            cur = []
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    # some leaflets list sites without separators: a line that is exactly a country name closes a site
    split = []
    for b in blocks:
        cur = []
        for ln in b:
            cur.append(ln)
            if norm_text(ln).strip(" .,;:()") in NAME_TO_ISO:
                split.append(cur)
                cur = []
        if cur:
            split.append(cur)
    blocks = split
    sites = []
    for b in blocks:
        b = [x for x in b if not re.match(r"^\(?(s[oó]lo|only|uniquement|nur)\b.*\)?$", x, re.I)]
        while b and FORM_HEADER.match(b[0]):  # dosage-form sub-headings in Annex IIA are not companies
            b = b[1:]
        if not b or len(b) < 2 or not re.match(r"^[\w\"“(]", b[0]) or b[0][:1].islower():
            continue  # a site needs a company line plus at least one address line
        if not b:
            continue
        iso, basis = country_of(b)
        if iso is None and home_country and any(re.match(r"^\d{5}\s+\S", x) for x in b[1:]):
            iso, basis = home_country, f"derived: Inlandsadresse ohne Länderzeile im {home_country}-Leaflet, 5-stellige PLZ"
        sites.append(dict(company=b[0], address=", ".join(b[1:]), country=iso, country_basis=basis,
                          quote=heading + "\n" + "\n".join(b)))
    return sites
