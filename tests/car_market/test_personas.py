from car_market.personas import Persona, load_personas, utility
from car_market.generator import CarSpec


def _fake_car(**overrides):
    base = dict(
        car_id="C_0001", year=2020, make="Honda", model="CR-V",
        body="SUV", mileage=40000, true_condition=4.0, true_value=22000.0,
        seller_floor=19800.0, seller_ceiling=24200.0,
        true_vhr_flags=["NO_SALVAGE_TITLE", "NO_ACCIDENTS_REPORTED", "NO_ONE_OWNER"],
    )
    base.update(overrides)
    return CarSpec(**base)


def test_load_personas_returns_ten():
    ps = load_personas()
    assert len(ps) == 10
    assert all(isinstance(p, Persona) for p in ps)


def test_persona_required_fields():
    ps = load_personas()
    for p in ps:
        assert p.persona_id
        assert p.allowed_bodies
        assert p.max_budget > 0
        assert "year" in p.weights and "miles" in p.weights and "condition" in p.weights


def test_utility_respects_hard_constraints():
    ps = {p.persona_id: p for p in load_personas()}
    student = ps["student_first_car"]
    expensive_car = _fake_car(true_value=40000.0)
    u = utility(expensive_car, listing_condition=4.0, price=39000.0, persona=student)
    assert u == float("-inf"), "should be ruled out by budget"


def test_utility_uses_listing_condition_not_true():
    ps = {p.persona_id: p for p in load_personas()}
    family = ps["family_of_four"]
    car = _fake_car()
    u_high = utility(car, listing_condition=5.0, price=20000.0, persona=family)
    u_low = utility(car, listing_condition=2.0, price=20000.0, persona=family)
    assert u_high > u_low, "buyer values higher claimed condition"


def test_utility_decreasing_in_price():
    ps = {p.persona_id: p for p in load_personas()}
    family = ps["family_of_four"]
    car = _fake_car()
    u_cheap = utility(car, 4.0, 18000.0, family)
    u_dear = utility(car, 4.0, 23000.0, family)
    assert u_cheap > u_dear
