import pytest
from car_market.reputation import (
    BetaReputation, update_on_deal, honesty_from_gap,
)


def test_initial_state():
    r = BetaReputation(seller_id="S_01")
    assert r.alpha == 2.0 and r.beta == 2.0
    assert r.review_count == 0
    assert abs(r.mean_rating() - 0.5) < 1e-9


def test_honesty_signal_extremes():
    assert honesty_from_gap(0.0) == 1.0
    assert honesty_from_gap(2.0) == 0.0
    assert honesty_from_gap(4.0) == 0.0   # clipped


def test_update_increases_alpha_on_honest_deal():
    r = BetaReputation(seller_id="S_01")
    update_on_deal(r, listing_cond=3.0, true_cond=3.0)
    assert r.alpha > 2.0
    assert r.beta < 2.001    # decay drag minus tiny new contribution


def test_update_increases_beta_on_dishonest_deal():
    r = BetaReputation(seller_id="S_01")
    update_on_deal(r, listing_cond=5.0, true_cond=2.0)  # gap=3 → honesty clipped to 0
    assert r.beta > 2.0
    assert r.alpha < 2.001


def test_decay_within_bounds():
    r = BetaReputation(seller_id="S_01", decay=0.95)
    update_on_deal(r, listing_cond=3.0, true_cond=3.0)
    a1, b1 = r.alpha, r.beta
    update_on_deal(r, listing_cond=3.0, true_cond=3.0)
    a2, b2 = r.alpha, r.beta
    assert a2 > a1
    # Beta should stay low because both updates were honest (h=1, so β contribution=0).
    # Decay drags β from 2.0 → 1.9 → 1.805.
    assert b2 < 2.1


def test_review_count_increments():
    r = BetaReputation(seller_id="S_01")
    for _ in range(5):
        update_on_deal(r, listing_cond=3.0, true_cond=3.0)
    assert r.review_count == 5


def test_stars_range():
    r = BetaReputation(seller_id="S_01")
    assert 1.0 <= r.stars() <= 5.0


def test_excerpt_factory_called_on_dishonest():
    r = BetaReputation(seller_id="S_01")
    captured = []
    def fac(listing_cond, true_cond):
        captured.append((listing_cond, true_cond))
        return f"misleading by {listing_cond - true_cond:.1f}"
    update_on_deal(r, listing_cond=5.0, true_cond=2.0, excerpt_factory=fac)
    assert len(captured) == 1
    assert len(r.excerpts) == 1
    assert "misleading" in r.excerpts[0]


def test_excerpt_capped_at_five():
    r = BetaReputation(seller_id="S_01")
    def fac(**kw): return "bad"
    for _ in range(10):
        update_on_deal(r, listing_cond=5.0, true_cond=2.0, excerpt_factory=fac)
    assert len(r.excerpts) == 5
