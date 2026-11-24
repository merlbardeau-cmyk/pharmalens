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
    re.compile(r"^Hersteller(in)?\s*:?$", re.I),                                             # DE/CH/AT
    re.compile(r"^Fabrikant(en)?( vrijgifte)?\s*:?$", re.I),                                  # NL
    re.compile(r"^Fremstiller(e)?\s*:?$", re.I),                                              # DK
]
COMBINED = re.compile(r"^Titular de la autorizaci[oó]n de comercializaci[oó]n y responsable de la fabricaci[oó]n\s*:?$", re.I)
STOP = re.compile(
    r"^(Pueden solicitar|Representante local|Fecha de la [uú]ltima revisi[oó]n|Este medicamento est[aá] autorizado|"
    r"La informaci[oó]n detallada|Otras fuentes|Puede solicitar|Fecha de la|Este prospecto|Este medicamento|Otras presentaciones|Fecha de [uú]ltima|"
    r"Noms du m[ée]dicament|Ce m[ée]dicament est autoris|La derni[eè]re date|Date d.approbation|Autres sources|"
    r"Repr[ée]sentant|Pour toute information|Conformément à la réglementation|"
    r"B\.$|C\.$|B\. CONDITIONS|B\.\s+CONDITIONS|CONDITIONS OR RESTRICTIONS|The printed package leaflet|Name and address of the manufacturer.* biological|C\. OTHER CONDITIONS|"
    r"This leaflet was last revised|For any information|Marketing Authorisation Holder|"
    r"Titular de la autorizaci[oó]n|Titulaire de l.autorisation|Exploitant|"
    r"Dit geneesmiddel is|In het register ingeschreven|Voor informatie en inlichtingen|Registratiehouder|"
    r"Houder van de vergunning|Deze bijsluiter is|Neem voor alle informatie|Dit middel is|"
    r"Pharmazeutischer Unternehmer|Zulassungsinhaber|Diese Packungsbeilage wurde|Z\.Nr\.|Zulassungsnummer|"
    r"Indehaver af markedsf|Denne indl[æa]gsseddel blev|Repr[æa]sentant|Lokal repr)", re.I)
FORM_HEADER = re.compile(r"^(film-coated |prolonged-release |gastro-resistant |hard |soft |orodispersible )?"
                         r"(tablets?|capsules?|granules|powder|solution|suspension|injection|concentrate|pens?|syringes?|"
                         r"solution for injection.*|granules in capsules.*|oral .*)\b.{0,60}$", re.I)
CONTACT = re.compile(r"@|\b(tel|t[eé]l[eé]phone|tfno|phone|fax|e-?mail|correo)\b\.?\s*:?|https?://|www\.", re.I)
SEP = re.compile(r"^(o|ó|ou|or|oder|y|et|and|en|of|eller|og|und)(\s*\(.{0,80}\))?\s*:?$", re.I)
MAX_LINES = 120


STREET = re.compile(r"\b(avenue|av\.|avda|avd\.|rue|calle|c/|via|viale|street|st\.|road|rd\.|strasse|str\.|stra[sß]e|ul\.|ulica|"
                    r"boulevard|bd|plaza|place|camino|carretera|ctra|pol[ií]gono|route|chemin|allee|weg)\b", re.I)


def closes_site(ln: str) -> bool:
    """line ends a site address: '..., España' / '... (ESPAÑA)' / '62-020 Swarzedz Polonia' - not 'avenue de France'."""
    t = norm_text(ln).strip(" .;:")
    m = re.search(r"[,–\-(]\s*([a-z .'-]+?)\)?$", t)
    if m and m.group(1).strip() in NAME_TO_ISO:
        return True
    if re.search(r"\b\d{4,5}\b|\b\d{2}-\d{3}\b", t) and not STREET.search(t):
        words = t.split()
        return any(len(words) > k and " ".join(words[-k:]) in NAME_TO_ISO and len(" ".join(words[-k:])) > 3 for k in (1, 2, 3))
    return False


def html_to_lines(text: str) -> list[str]:
    text = re.sub(r"<(script|style).*?</\1>", "", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>|</h\d>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", text))
    return [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln.strip() and ln.strip() != "\xa0"]


INLINE = re.compile(r"^(Fabrikant(?:en)?|Fabricante|Fabricant|Manufacturer|Hersteller|Fremstiller)\s*:\s*(\S.{2,})$", re.I)
NOISE = re.compile(r"^(Module \d+\b.*|Administrative information|and prescribing information|Page \d+ of \d+|Pagina \d+ van \d+|Seite \d+ von \d+|Side \d+ af \d+)$", re.I)
HOUSE_NO = re.compile(r"\b\d+[a-z]?\s*$|^\d")


def split_inline(lines: list[str]) -> list[str]:
    out = []
    for ln in lines:
        if NOISE.match(ln):
            continue
        m = INLINE.match(ln)
        if m:
            out += [m.group(1) + ":", m.group(2)]
        else:
            out.append(ln)
    return out


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
    lines = split_inline(lines)
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
            single_line_site = len(cur) == 1 and ln.count(",") >= 3 and closes_site(ln)
            ends_with_country = norm_text(ln).strip(" .,;:()") in NAME_TO_ISO or single_line_site or (len(cur) >= 2 and closes_site(ln))
            if ends_with_country:
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
        if len(b) == 1 and b[0].count(",") >= 3 and closes_site(b[0]):
            parts = [x.strip() for x in b[0].split(",")]
            k = next((i for i, x in enumerate(parts) if re.search(r"\d", x)), len(parts))
            company = ", ".join(parts[:max(k, 1)]).strip()
            iso, basis = country_of(b)
            sites.append(dict(company=company, address=", ".join(parts[max(k, 1):]), country=iso, country_basis=basis,
                              quote=heading + "\n" + b[0]))
            continue
        if b and (STREET.search(b[0]) or HOUSE_NO.search(b[0])) and not re.search(r"\b(gmbh|ag|s\.?a|ltd|limited|b\.?v|kft|d\.?d|s\.?r\.?l|s\.?p\.?a|a/s|inc|llc|plc|sp\. z|zrt|ehf|oy|ab)\b", b[0], re.I):
            continue  # first line is an address, not a company (column layout) -> no guess
        if not b or len(b) < 2 or len(b[0]) < 3 or not re.match(r"^[\w\"“(]", b[0]) or b[0][:1].islower():
            continue  # a site needs a company line plus at least one address line
        if not b:
            continue
        iso, basis = country_of(b)
        if iso is None and home_country and any(re.match(r"^\d{5}\s+\S", x) for x in b[1:]):
            iso, basis = home_country, f"derived: Inlandsadresse ohne Länderzeile im {home_country}-Leaflet, 5-stellige PLZ"
        sites.append(dict(company=b[0], address=", ".join(b[1:]), country=iso, country_basis=basis,
                          quote=heading + "\n" + "\n".join(b)))
    return sites
