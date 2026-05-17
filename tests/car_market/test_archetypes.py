import random
from car_market.archetypes import (
    SellerArchetype, HONEST, MODERATE, AGGRESSIVE,
    population_sample, build_listing,
)
from car_market.generator import generate


def test_archetype_constants():
    assert HONEST.condition_bias == 0.0
    assert MODERATE.condition_bias == 1.0
    assert AGGRESSIVE.condition_bias == 2.0


def test_population_proportions():
    pop = population_sample(seed=0, k=20)
    counts = {"honest": 0, "moderate": 0, "aggressive": 0}
    for a in pop:
        counts[a.name] += 1
    assert counts == {"honest": 12, "moderate": 6, "aggressive": 2}


def test_population_deterministic():
    assert [a.name for a in population_sample(seed=1, k=20)] == \
           [a.name for a in population_sample(seed=1, k=20)]


def test_honest_listing_matches_truth():
    car = generate(seed=0, n=1)[0]
    listing = build_listing(car, HONEST, seller_id="S_01", rng=random.Random(0))
    assert listing.listing_condition == car.true_condition
    assert set(listing.claimed_vhr_flags) == set(car.true_vhr_flags)


def test_moderate_inflates_condition():
    car = generate(seed=0, n=1)[0]
    listing = build_listing(car, MODERATE, seller_id="S_01", rng=random.Random(0))
    expected_cond = min(car.true_condition + 1.0, 5.0)
    assert abs(listing.listing_condition - expected_cond) < 1e-9


def test_aggressive_drops_negative_flags():
    # Use seed=42 to get a car with some negative flags
    car = None
    from car_market.generator import NEGATIVE_FLAGS
    for s in range(50):
        c = generate(seed=s, n=1)[0]
        if any(f in NEGATIVE_FLAGS for f in c.true_vhr_flags):
            car = c
            break
    assert car is not None, "should find a car with negative flags in 50 seeds"
    listing = build_listing(car, AGGRESSIVE, seller_id="S_01", rng=random.Random(0))
    for f in listing.claimed_vhr_flags:
        assert f not in NEGATIVE_FLAGS, f"aggressive should hide {f}"


def test_asking_price_within_shared_margin_band():
    """Asking = hedonic_value(claimed_cond) × margin, with margin in the
    shared [MARGIN_LOW, MARGIN_HIGH] band for all archetypes. The realized
    *markup over true_value* is the emergent variable — that's what we
    measure post-hoc, not what we hardcode."""
    from car_market.archetypes import MARGIN_LOW, MARGIN_HIGH
    from car_market.generator import hedonic_value
    car = generate(seed=2, n=1)[0]
    for arch in (HONEST, MODERATE, AGGRESSIVE):
        listing = build_listing(car, arch, seller_id="S_01", rng=random.Random(0))
        fair = hedonic_value(car.year, car.mileage, listing.listing_condition,
                                car.make, car.body)
        assert MARGIN_LOW * fair <= listing.asking_price <= MARGIN_HIGH * fair


def test_aggressive_asks_more_than_honest_on_same_car():
    """Sanity check: same car + same rng seed → aggressive seller's asking
    price > honest seller's. The difference comes from the claimed-condition
    shift, NOT from a baked-in markup."""
    car = generate(seed=0, n=1)[0]
    a_honest = build_listing(car, HONEST, "S_01", random.Random(0))
    a_aggr = build_listing(car, AGGRESSIVE, "S_02", random.Random(0))
    assert a_aggr.asking_price > a_honest.asking_price
