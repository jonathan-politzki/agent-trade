import random
import pytest

from car_market.archetypes import HONEST, AGGRESSIVE, build_listing
from car_market.generator import generate
from car_market.marketplace import CarMarketplace
from car_market.reputation import BetaReputation


def _seed_listings(mp, n=3, seed=0, archetype=HONEST, seller_id="S_01"):
    cars = generate(seed=seed, n=n)
    rng = random.Random(seed)
    for c in cars:
        l = build_listing(c, archetype, seller_id=seller_id, rng=rng)
        mp.add_listing(l)
    return cars


def test_listing_locks_on_open_offer():
    mp = CarMarketplace(run_name="t1")
    _seed_listings(mp, n=1)
    listing_id = list(mp.listings.keys())[0]
    off = mp.make_offer(buyer="B_01", listing_id=listing_id, price=10000.0, message="")
    assert off is not None
    second = mp.make_offer(buyer="B_02", listing_id=listing_id, price=11000.0, message="")
    assert second is None, "listing should be locked while offer is open"


def test_listing_unlocks_on_decline():
    mp = CarMarketplace(run_name="t2")
    _seed_listings(mp, n=1, seller_id="S_01")
    listing_id = list(mp.listings.keys())[0]
    off = mp.make_offer(buyer="B_01", listing_id=listing_id, price=10000.0, message="")
    mp.respond_to_offer(seller="S_01", offer_id=off.offer_id, action="decline",
                          counter_price=None, message="")
    re_offer = mp.make_offer(buyer="B_02", listing_id=listing_id, price=10500.0, message="")
    assert re_offer is not None, "lock should release after decline"


def test_buyer_cannot_hold_two_open_offers():
    mp = CarMarketplace(run_name="t3")
    _seed_listings(mp, n=2, seller_id="S_01")
    ids = list(mp.listings.keys())
    a = mp.make_offer(buyer="B_01", listing_id=ids[0], price=1000.0, message="")
    b = mp.make_offer(buyer="B_01", listing_id=ids[1], price=1000.0, message="")
    assert a is not None
    assert b is None, "buyer with an open offer cannot start another"


def test_buyer_can_make_offer_after_withdraw():
    mp = CarMarketplace(run_name="t3b")
    _seed_listings(mp, n=2, seller_id="S_01")
    ids = list(mp.listings.keys())
    a = mp.make_offer(buyer="B_01", listing_id=ids[0], price=1000.0, message="")
    assert a is not None
    mp.buyer_withdraw("B_01")
    b = mp.make_offer(buyer="B_01", listing_id=ids[1], price=1500.0, message="")
    assert b is not None


def test_search_ranking_visible_promotes_high_rep():
    mp = CarMarketplace(run_name="t4", reputation_gamma=0.5)
    _seed_listings(mp, n=1, seller_id="S_high")
    _seed_listings(mp, n=1, seed=1, seller_id="S_low")
    mp.reputation["S_high"] = BetaReputation("S_high", alpha=10.0, beta=2.0)
    mp.reputation["S_low"] = BetaReputation("S_low", alpha=2.0, beta=10.0)
    results = mp.search(query="SUV", max_results=10)
    high_idx = next((i for i, r in enumerate(results) if r.seller_id == "S_high"), None)
    low_idx = next((i for i, r in enumerate(results) if r.seller_id == "S_low"), None)
    assert high_idx is not None and low_idx is not None
    assert high_idx < low_idx, "visible mode should rank high-rep above low-rep"


def test_search_ranking_hidden_ignores_rep():
    mp = CarMarketplace(run_name="t5", reputation_gamma=0.0)
    _seed_listings(mp, n=1, seller_id="S_A")
    _seed_listings(mp, n=1, seed=1, seller_id="S_B")
    mp.reputation["S_A"] = BetaReputation("S_A", alpha=10.0, beta=2.0)
    mp.reputation["S_B"] = BetaReputation("S_B", alpha=2.0, beta=10.0)
    # In hidden mode, rating shouldn't matter — order determined by relevance + tiebreak.
    # We assert seller_stars is 0 in result cards (cf. spec: hidden mode hides stars).
    results = mp.search(query="SUV", max_results=10)
    for r in results:
        assert r.seller_stars == 0.0


def test_lookup_seller_hidden_returns_none():
    mp = CarMarketplace(run_name="t6", reputation_gamma=0.0)
    _seed_listings(mp, n=1, seller_id="S_01")
    assert mp.lookup_seller("S_01") is None


def test_lookup_seller_visible_returns_card():
    mp = CarMarketplace(run_name="t7", reputation_gamma=0.5)
    _seed_listings(mp, n=1, seller_id="S_01")
    card = mp.lookup_seller("S_01")
    assert card is not None
    assert card.seller_id == "S_01"
    assert 1.0 <= card.stars <= 5.0


def test_accept_settles_and_updates_reputation():
    mp = CarMarketplace(run_name="t8")
    cars = _seed_listings(mp, n=1, archetype=AGGRESSIVE, seller_id="S_01")
    listing_id = list(mp.listings.keys())[0]
    car = cars[0]
    off = mp.make_offer(buyer="B_01", listing_id=listing_id, price=car.true_value, message="")
    deal = mp.respond_to_offer(seller="S_01", offer_id=off.offer_id, action="accept",
                                  counter_price=None, message="")
    assert deal is not None
    assert deal.price == car.true_value
    # Listing is sold.
    assert mp.listings[listing_id].sold is True
    # Reputation updated; aggressive sellers misrepresent (listing_cond = true_cond + 2),
    # so honesty signal is 0 and beta grows.
    rep = mp.reputation["S_01"]
    assert rep.review_count == 1
    assert rep.beta > 2.0
