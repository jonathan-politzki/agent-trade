from car_market.generator import CarSpec, generate


def test_carspec_fields():
    cs = CarSpec(
        car_id="C_0001", year=2018, make="Honda", model="Accord",
        body="Sedan", mileage=78000, true_condition=3.2,
        true_value=15400.0, seller_floor=13860.0, seller_ceiling=16940.0,
        true_vhr_flags=["NO_SALVAGE_TITLE", "NO_ACCIDENTS_REPORTED"],
    )
    assert cs.year == 2018
    assert cs.seller_floor < cs.true_value < cs.seller_ceiling
    assert cs.true_condition >= 1.0 and cs.true_condition <= 5.0


def test_generate_is_deterministic():
    a = generate(seed=42, n=20)
    b = generate(seed=42, n=20)
    assert [c.car_id for c in a] == [c.car_id for c in b]
    assert [c.true_value for c in a] == [c.true_value for c in b]


def test_generate_attribute_ranges():
    cars = generate(seed=7, n=100)
    assert all(2010 <= c.year <= 2026 for c in cars)
    assert all(0 <= c.mileage <= 250000 for c in cars)
    assert all(1.0 <= c.true_condition <= 5.0 for c in cars)
    assert all(c.true_value > 0 for c in cars)
    assert all(c.seller_floor < c.true_value < c.seller_ceiling for c in cars)
