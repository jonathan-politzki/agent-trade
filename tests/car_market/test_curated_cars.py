from car_market.generator import load_curated_cars, hedonic_value


def test_load_curated_cars_returns_25():
    cars = load_curated_cars()
    assert len(cars) == 25


def test_curated_car_value_within_hedonic_range():
    cars = load_curated_cars()
    for c in cars:
        expected = hedonic_value(c.year, c.mileage, c.true_condition, c.make, c.body)
        assert 0.7 * expected <= c.true_value <= 1.3 * expected, \
            f"{c.car_id} true_value {c.true_value} far from hedonic {expected}"


def test_curated_cars_unique_ids():
    cars = load_curated_cars()
    ids = [c.car_id for c in cars]
    assert len(set(ids)) == len(ids)


def test_curated_cars_floor_ceiling_invariant():
    cars = load_curated_cars()
    for c in cars:
        assert c.seller_floor < c.true_value < c.seller_ceiling
