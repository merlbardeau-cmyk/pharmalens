from graph.export_manufacturer import normalise, possible_parent


def test_normalise_keeps_legal_forms_and_acronyms():
    assert normalise("ZHEJIANG HUAHAI PHARMACEUTICAL CO LTD") == "Zhejiang Huahai Pharmaceutical Co. Ltd."
    assert normalise("TAPI NL B.V.") == "TAPI NL B.V."
    assert normalise("MSN LIFE SCIENCES PRIVATE LTD") == "MSN Life Sciences Private Ltd."


def test_possible_parent_only_when_a_company_follows_the_group():
    assert possible_parent("YANGTZE RIVER PHARMACEUTICAL GROUP JIANGSU HAICI BIOLOGICAL PHARMACEUTICAL CO LTD") == "Yangtze River Pharmaceutical Group"
    assert possible_parent("QILU PHARMACEUTICAL GROUP CO LTD") is None
    assert possible_parent("AUROBINDO PHARMA LTD") is None
