"""Buyer personas with hedonic utility. Personas are loaded from
car_market/personas_data/*.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .generator import CarSpec


@dataclass(frozen=True)
class Persona:
    persona_id: str               # machine-readable slug
    description: str              # 1-3 sentence character description
    allowed_bodies: list[str]     # hard constraint
    max_miles: int                # hard constraint
    max_age_years: int            # hard constraint, vs base_year=2026
    max_budget: float             # hard constraint
    preferred_makes: list[str]    # soft preference
    weights: dict                 # keys: year, miles, condition, body_match, brand
    price_sensitivity: float      # λ; higher = more price-averse
    risk_aversion: float          # 0..1; penalty for high asking-price-vs-ceiling
    name: str                     # human-readable name for transcripts


PERSONA_DIR = Path(__file__).parent / "personas_data"
BASE_YEAR = 2026


def load_personas() -> list[Persona]:
    out = []
    for p in sorted(PERSONA_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        out.append(Persona(**d))
    return out


def _satisfies(car: CarSpec, p: Persona, price: float) -> bool:
    if car.body not in p.allowed_bodies:
        return False
    if car.mileage > p.max_miles:
        return False
    if (BASE_YEAR - car.year) > p.max_age_years:
        return False
    if price > p.max_budget:
        return False
    return True


def welfare_value(car: CarSpec, condition: float, persona: Persona) -> float:
    """Persona's gross max WTP for a car of a given condition, ignoring any
    constraint check. Returns dollars. Used by the evaluator as the "U(car |
    persona)" term in spec §9.1 welfare formulas. The buyer's max willingness
    to pay equals dollar_value / price_sensitivity (the price at which net
    utility crosses zero)."""
    w = persona.weights
    year_score = (car.year - 2015) / 11.0          # 2015→0, 2026→1
    miles_score = 1.0 - min(1.0, car.mileage / 150000)
    cond_score = (condition - 1.0) / 4.0
    body_match = 1.0 if car.body in persona.allowed_bodies else 0.0
    brand_match = 1.0 if car.make in persona.preferred_makes else 0.4
    value = (
        w["year"] * year_score
        + w["miles"] * miles_score
        + w["condition"] * cond_score
        + w["body_match"] * body_match
        + w["brand"] * brand_match
    )
    dollar_value = value * persona.max_budget
    return float(dollar_value / max(0.1, persona.price_sensitivity))


def utility(car: CarSpec, listing_condition: float, price: float, persona: Persona) -> float:
    """Net utility for buying `car` at `price` given the seller's claim
    `listing_condition`. Buyer does NOT see true_condition; she decides based
    on listing_condition. Returns -inf if hard constraints fail. Sign-positive
    means the buyer would want to bid; negative means walk away.

    Defined as `welfare_value(car, listing_condition, persona) - price`, i.e.
    max-WTP minus price. This is the buyer's *decision* signal, distinct from
    *ex-post* welfare (which uses true_condition, not listing_condition)."""
    if not _satisfies(car, persona, price):
        return float("-inf")
    return welfare_value(car, listing_condition, persona) - price
