import random
from car_market.policies import (
    HeuristicSeller, HeuristicBuyer, NegotiationStep,
)
from car_market.archetypes import HONEST, AGGRESSIVE
from car_market.generator import generate
from car_market.personas import load_personas


def test_seller_accepts_offer_at_ceiling():
    car = generate(seed=0, n=1)[0]
    seller = HeuristicSeller(seller_id="S_01", archetype=HONEST, rng=random.Random(0))
    decision = seller.respond_to_offer(car=car, asking_price=car.seller_ceiling,
                                          offer_price=car.seller_ceiling * 1.01)
    assert decision.action == "accept"


def test_seller_declines_far_below_floor():
    car = generate(seed=0, n=1)[0]
    seller = HeuristicSeller(seller_id="S_01", archetype=HONEST, rng=random.Random(0))
    decision = seller.respond_to_offer(car=car, asking_price=car.seller_ceiling,
                                          offer_price=car.seller_floor * 0.5)
    assert decision.action in ("decline", "counter")


def test_seller_counters_above_floor_below_split():
    car = generate(seed=0, n=1)[0]
    seller = HeuristicSeller(seller_id="S_01", archetype=HONEST, rng=random.Random(0))
    # An offer exactly at reservation (floor * greed=1.00) but below split should counter.
    reservation = car.seller_floor * 1.00
    asking = car.seller_ceiling
    split = (reservation + asking) / 2
    decision = seller.respond_to_offer(car=car, asking_price=asking,
                                          offer_price=reservation + 1.0)
    # offer >= reservation but < split should counter
    if reservation + 1.0 < split:
        assert decision.action == "counter"
        assert decision.counter_price > 0


def test_buyer_ranks_listings_by_utility():
    cars = generate(seed=42, n=10)
    persona = next(p for p in load_personas() if p.persona_id == "family_of_four")
    buyer = HeuristicBuyer(buyer_id="B_01", persona=persona, rng=random.Random(0))
    from car_market.marketplace import ListingCard
    cards = [
        ListingCard(
            listing_id=f"L_{i}", seller_id="S_X",
            year=c.year, make=c.make, model=c.model, body=c.body,
            mileage=c.mileage, listing_condition=c.true_condition,
            asking_price=c.true_value * 1.05, seller_stars=3.0,
        ) for i, c in enumerate(cars)
    ]
    cars_by_id = {f"L_{i}": c for i, c in enumerate(cars)}
    ranked = buyer.rank_listings(cards, cars_by_id)
    if ranked:
        top_card = next(c for c in cards if c.listing_id == ranked[0])
        assert top_card.body in persona.allowed_bodies


def test_buyer_propose_price_respects_budget():
    car = generate(seed=0, n=1)[0]
    persona = next(p for p in load_personas() if p.persona_id == "student_first_car")
    buyer = HeuristicBuyer(buyer_id="B_01", persona=persona, rng=random.Random(0))
    from car_market.marketplace import ListingCard
    card = ListingCard(
        listing_id="L_1", seller_id="S_X",
        year=car.year, make=car.make, model=car.model, body=car.body,
        mileage=car.mileage, listing_condition=car.true_condition,
        asking_price=99999.0, seller_stars=3.0,
    )
    bid = buyer.propose_price(card, car)
    assert bid <= persona.max_budget


def test_negotiation_step_has_required_fields():
    step = NegotiationStep(action="accept")
    assert step.action == "accept"
    assert step.counter_price == 0.0
