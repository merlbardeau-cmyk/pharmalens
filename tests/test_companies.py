import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from resolve.companies import legal_key, normalise  # noqa: E402


def test_same_entity_spelling_variants_merge():
    assert legal_key("Sandoz Farmaceutica S.A.") == legal_key("Sandoz Farmacéutica, S.A.")
    assert legal_key("Sandoz Ltd") == legal_key("Sandoz Limited")
    assert legal_key("Sandoz Gmbh") == legal_key("SANDOZ GMBH")


def test_different_legal_entities_stay_apart():
    keys = {legal_key(n) for n in ["Sandoz GmbH", "Sandoz A/S", "Sandoz Pharmaceuticals AG", "Sandoz B.V.", "SANDOZ"]}
    assert len(keys) == 5


def test_legal_forms():
    assert normalise("Zydus Lifesciences Private Limited") == ("ZYDUS LIFESCIENCES", "PVT LTD")
    assert normalise("Sandoz Polska Sp. Z O.O.")[1] == "SPZOO"
    assert normalise("Lek d.d.")[1] == "DD"
    assert normalise("TEVA (PAYS-BAS)") == ("TEVA", None)
