from car_market.sellers import load_sellers


def test_load_sellers_returns_ten():
    s = load_sellers()
    assert len(s) == 10


def test_population_proportions():
    s = load_sellers()
    counts = {"honest": 0, "moderate": 0, "aggressive": 0}
    for p in s:
        counts[p.archetype_name] += 1
    assert counts == {"honest": 6, "moderate": 3, "aggressive": 1}


def test_archetype_property_resolves():
    s = load_sellers()
    for p in s:
        a = p.archetype
        assert a.name == p.archetype_name


def test_unique_seller_ids():
    s = load_sellers()
    ids = [p.seller_id for p in s]
    assert len(set(ids)) == len(ids)
