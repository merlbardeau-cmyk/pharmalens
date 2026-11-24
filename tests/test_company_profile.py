from enrich.company_profile import same_group


def test_same_group_via_shared_parent():
    g = {1: {10}, 2: {10}, 3: {11}, 10: {10}}
    assert same_group(g, 1, 2)
    assert same_group(g, 10, 1)          # parent vs child
    assert not same_group(g, 1, 3)
    assert same_group(g, 5, 5)
    assert not same_group(g, 5, 6)       # unknown companies are not grouped
