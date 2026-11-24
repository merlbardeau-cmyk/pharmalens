"""Pilot set (Phase 1): 20 APIs.

`match` = regex on unaccented, lower-cased substance text from any register (DE/FR/ES/IT/EN/TR).
It deliberately catches language variants (metformine, metformina, levotiroxina) and salt
spellings, and excludes known false friends (esomeprazole vs omeprazole).
For the full 4'600 roll-out this hand list is replaced by multilingual INN lists (EVMPD/xEVMPD).
"""

PILOT = [
    # inn, group, match regex
    ("metformin", "blockbuster", r"metformin"),
    ("atorvastatin", "blockbuster", r"atorvastatin"),
    ("amlodipine", "blockbuster", r"amlodipin"),
    ("omeprazole", "blockbuster", r"(?<!es)omeprazol"),
    ("levothyroxine", "blockbuster", r"levo-?t[hy]*[iy]ro[xs]in"),
    ("pyridostigmine", "niche", r"p[iy]ridostigmin"),
    ("dapsone", "niche", r"dapson"),
    ("fludrocortisone", "niche", r"fludrocortison"),
    ("mexiletine", "niche", r"mexiletin"),
    ("hydroxycarbamide", "niche", r"h[iy]dro[xs]+[iy]carbamid|idrossicarbamid|hydroxyurea|hydroxyharnstoff|hidroxiurea"),
    ("florfenicol", "veterinary", r"florfenicol"),
    ("tulathromycin", "veterinary", r"tulat(h)?romicin|tulathromycin"),
    ("toltrazuril", "veterinary", r"toltrazuril"),
    ("pimobendan", "veterinary", r"pimobendan"),
    ("marbofloxacin", "veterinary", r"marbofloxacin"),
    ("apixaban", "patent", r"apixaban"),
    ("empagliflozin", "patent", r"empagliflozin"),
    ("sacubitril", "patent", r"sacubitril"),
    ("edoxaban", "patent", r"edoxaban"),
    ("semaglutide", "patent", r"semaglutid"),
]

# GSRS preferred-name overrides where the US name differs from the INN
GSRS_NAME: dict[str, str] = {}
