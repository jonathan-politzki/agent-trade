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


def test_asking_price_within_archetype_band():
    car = generate(seed=2, n=1)[0]
    listing = build_listing(car, MODERATE, seller_id="S_01", rng=random.Random(0))
    lo = car.seller_ceiling * 1.05
    hi = car.seller_ceiling * 1.15
    assert lo <= listing.asking_price <= hi
