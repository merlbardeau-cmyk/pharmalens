import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from resolve.groups import stem


def test_stems():
    assert stem("SANDOZ FARMACEUTICA") == "SANDOZ" == stem("SANDOZ")
    assert stem("LABORATORIOS NORMON") == "LABORATORIOS NORMON"
    assert stem("LABORATORIOS CINFA") != stem("LABORATORIOS NORMON")
    assert stem("PHARMA") is None and stem("ABC") is None


def test_homonyms_and_geo_prefixes():
    assert stem("MERCK SHARP & DOHME") == stem("MERCK & CO") == "MSD (Merck & Co.)"
    assert stem("MERCK KGAA") == stem("MERCK HEALTHCARE") == "MERCK KGAA"
    assert stem("ZHEJIANG HUAHAI PHARMACEUTICAL CO") == "ZHEJIANG HUAHAI" != stem("ZHEJIANG HISUN PHARMACEUTICAL CO")
