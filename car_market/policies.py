"""Heuristic policies used in `--mode fast`. Deterministic given rng seed.
No LLM calls. These are what produce the headline ablation chart."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .archetypes import SellerArchetype
from .generator import CarSpec
from .marketplace import ListingCard
from .personas import Persona, utility


@dataclass
class NegotiationStep:
    action: str               # accept | decline | counter
    counter_price: float = 0.0
    rationale: str = ""


class HeuristicSeller:
    def __init__(self, seller_id: str, archetype: SellerArchetype, rng: random.Random):
        self.seller_id = seller_id
        self.archetype = archetype
        self.rng = rng

    def respond_to_offer(self, car: CarSpec, asking_price: float, offer_price: float) -> NegotiationStep:
        greed = {"honest": 1.00, "moderate": 1.03, "aggressive": 1.06}[self.archetype.name]
        reservation = car.seller_floor * greed
        if offer_price >= reservation:
            split = (reservation + asking_price) / 2.0
            if offer_price >= split:
                return NegotiationStep(action="accept",
                                          rationale=f"offer {offer_price:.0f} >= split {split:.0f}")
            else:
                return NegotiationStep(action="counter", counter_price=split,
                                          rationale="counter at split")
        return NegotiationStep(action="decline",
                                  rationale=f"offer {offer_price:.0f} < reservation {reservation:.0f}")


class HeuristicBuyer:
    def __init__(self, buyer_id: str, persona: Persona, rng: random.Random):
        self.buyer_id = buyer_id
        self.persona = persona
        self.rng = rng

    def rank_listings(self, cards: list[ListingCard], cars_by_id: dict[str, CarSpec]) -> list[str]:
        scored = []
        for c in cards:
            car = cars_by_id.get(c.listing_id)
            if car is None:
                continue
            u = utility(
                car=car, listing_condition=c.listing_condition,
                price=c.asking_price, persona=self.persona,
            )
            if u == float("-inf"):
                continue
            scored.append((u, c.listing_id))
        scored.sort(reverse=True)
        return [lid for _, lid in scored]

    def propose_price(self, card: ListingCard, car: CarSpec) -> float:
        """Bid below asking but above what we'd be willing to pay."""
        w = self.persona.weights
        year_score = (car.year - 2015) / 11.0
        miles_score = 1.0 - min(1.0, car.mileage / 150000)
        cond_score = (card.listing_condition - 1.0) / 4.0
        body_match = 1.0 if car.body in self.persona.allowed_bodies else 0.0
        brand_match = 1.0 if car.make in self.persona.preferred_makes else 0.4
        value = (w["year"] * year_score + w["miles"] * miles_score
                 + w["condition"] * cond_score + w["body_match"] * body_match
                 + w["brand"] * brand_match) * self.persona.max_budget
        wtp = value / max(0.1, self.persona.price_sensitivity)
        bid = 0.90 * min(wtp, card.asking_price)
        return float(min(bid, self.persona.max_budget))
