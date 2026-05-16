"""Seller archetypes. Pinned policies — sellers are NOT free to choose
inflation level. This makes the reputation ablation identifiable."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .generator import CarSpec, NEGATIVE_FLAGS


@dataclass(frozen=True)
class SellerArchetype:
    name: str                           # honest | moderate | aggressive
    condition_bias: float               # 0.0 | 1.0 | 2.0
    vhr_disclosure: str                 # full | drop_worst | drop_all_negative
    asking_markup_low: float
    asking_markup_high: float


HONEST = SellerArchetype("honest", 0.0, "full", 0.95, 1.05)
MODERATE = SellerArchetype("moderate", 1.0, "drop_worst", 1.05, 1.15)
AGGRESSIVE = SellerArchetype("aggressive", 2.0, "drop_all_negative", 1.10, 1.25)

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
    """Construct a CarListing from a CarSpec + archetype policy."""
    listing_cond = min(5.0, car.true_condition + archetype.condition_bias)
    claimed_flags = _disclose(car.true_vhr_flags, archetype.vhr_disclosure)
    markup = rng.uniform(archetype.asking_markup_low, archetype.asking_markup_high)
    asking = car.seller_ceiling * markup
    return CarListing(
        listing_id=listing_id or f"L_{car.car_id[2:]}_{seller_id}",
        seller_id=seller_id, car=car,
        asking_price=float(asking),
        listing_condition=float(listing_cond),
        claimed_vhr_flags=claimed_flags,
    )
