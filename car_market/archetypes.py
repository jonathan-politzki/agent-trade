"""Seller archetypes. Pinned policies on DISCLOSURE (condition + VHR flags),
not on pricing. Markup over fair-value-at-claimed-condition is drawn from a
SHARED distribution across all archetypes — we want to MEASURE how much
margin each archetype actually extracts, not bake it in as an input."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .generator import CarSpec, NEGATIVE_FLAGS, hedonic_value

# Shared profit-margin distribution. Every seller (honest, moderate, aggressive)
# samples from this range. Aggressive sellers naturally end up with higher
# asking prices because their CLAIMED condition shifts the hedonic anchor up,
# but their margin draw itself is from the same distribution. The realized
# markup-per-archetype is therefore an emergent variable — measure it in the
# post-hoc analysis.
MARGIN_LOW = 1.00
MARGIN_HIGH = 1.20


@dataclass(frozen=True)
class SellerArchetype:
    name: str                           # honest | moderate | aggressive
    condition_bias: float               # 0.0 | 1.0 | 2.0  — condition inflation
    vhr_disclosure: str                 # full | drop_worst | drop_all_negative


HONEST = SellerArchetype("honest", 0.0, "full")
MODERATE = SellerArchetype("moderate", 1.0, "drop_worst")
AGGRESSIVE = SellerArchetype("aggressive", 2.0, "drop_all_negative")

# Population proportions for k=20 sellers: 12 honest, 6 moderate, 2 aggressive.
_POPULATION_TEMPLATE = ([HONEST] * 12) + ([MODERATE] * 6) + ([AGGRESSIVE] * 2)


def population_sample(seed: int, k: int = 20) -> list[SellerArchetype]:
    """Deterministic archetype draw for k sellers. Keeps 60/30/10 proportions."""
    rng = random.Random(seed)
    if k == 20:
        out = _POPULATION_TEMPLATE[:]
    else:
        n_honest = int(round(0.60 * k))
        n_moderate = int(round(0.30 * k))
        n_aggressive = k - n_honest - n_moderate
        out = ([HONEST] * n_honest) + ([MODERATE] * n_moderate) + ([AGGRESSIVE] * n_aggressive)
    rng.shuffle(out)
    return out


@dataclass
class CarListing:
    """A listing produced by combining a CarSpec with a seller archetype."""
    listing_id: str
    seller_id: str
    car: CarSpec
    asking_price: float
    listing_condition: float
    claimed_vhr_flags: list[str]
    description: str = ""        # filled in `llm` mode only
    sold: bool = False


def _disclose(true_flags: list[str], policy: str) -> list[str]:
    if policy == "full":
        return list(true_flags)
    if policy == "drop_worst":
        # Drop a single negative flag if any; otherwise unchanged.
        negs = [f for f in true_flags if f in NEGATIVE_FLAGS]
        if not negs:
            return list(true_flags)
        drop = negs[0]
        return [f for f in true_flags if f != drop]
    if policy == "drop_all_negative":
        return [f for f in true_flags if f not in NEGATIVE_FLAGS]
    raise ValueError(f"unknown vhr_disclosure policy: {policy}")


def build_listing(
    car: CarSpec,
    archetype: SellerArchetype,
    seller_id: str,
    rng: random.Random,
    listing_id: str | None = None,
) -> CarListing:
    """Construct a CarListing.

    asking_price = hedonic_value(year, miles, claimed_condition, make, body)
                   × margin
    where margin ~ Uniform(MARGIN_LOW, MARGIN_HIGH) — shared across all
    archetypes. Aggressive sellers naturally ask more (because they CLAIM
    higher condition, lifting the hedonic anchor), but their margin itself
    is not archetype-baked. The realized markup-per-archetype is what we
    want to MEASURE in analysis."""
    listing_cond = min(5.0, car.true_condition + archetype.condition_bias)
    claimed_flags = _disclose(car.true_vhr_flags, archetype.vhr_disclosure)
    fair_at_claimed = hedonic_value(car.year, car.mileage, listing_cond,
                                       car.make, car.body)
    margin = rng.uniform(MARGIN_LOW, MARGIN_HIGH)
    asking = fair_at_claimed * margin
    return CarListing(
        listing_id=listing_id or f"L_{car.car_id[2:]}_{seller_id}",
        seller_id=seller_id, car=car,
        asking_price=float(asking),
        listing_condition=float(listing_cond),
        claimed_vhr_flags=claimed_flags,
    )
