"""Synthetic car generator. The oracle: every car's `true_value` is the
ground truth for regret/welfare computations. No external dataset is loaded
at runtime."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# Make/body marginal (hand-tuned to look like a real 2026 lot).
MAKE_BODY_PRIOR = [
    ("Honda",     "Sedan",       0.10),
    ("Honda",     "SUV",         0.06),
    ("Toyota",    "Sedan",       0.10),
    ("Toyota",    "SUV",         0.07),
    ("Toyota",    "Truck",       0.04),
    ("Ford",      "Truck",       0.07),
    ("Ford",      "SUV",         0.06),
    ("Chevrolet", "Truck",       0.06),
    ("Chevrolet", "SUV",         0.04),
    ("BMW",       "Sedan",       0.04),
    ("BMW",       "SUV",         0.03),
    ("Tesla",     "Sedan",       0.05),
    ("Tesla",    "SUV",         0.04),
    ("Subaru",    "SUV",         0.05),
    ("Mazda",     "Sedan",       0.04),
    ("Hyundai",   "Sedan",       0.03),
    ("Kia",       "SUV",         0.03),
    ("Jeep",      "SUV",         0.04),
    ("Nissan",    "Sedan",       0.03),
    ("Volkswagen","Sedan",       0.02),
]
MODELS_PER_MAKE_BODY = {
    ("Honda", "Sedan"): ["Civic", "Accord"],
    ("Honda", "SUV"): ["CR-V", "Pilot"],
    ("Toyota", "Sedan"): ["Corolla", "Camry"],
    ("Toyota", "SUV"): ["RAV4", "Highlander"],
    ("Toyota", "Truck"): ["Tacoma", "Tundra"],
    ("Ford", "Truck"): ["F-150", "Ranger"],
    ("Ford", "SUV"): ["Explorer", "Escape"],
    ("Chevrolet", "Truck"): ["Silverado", "Colorado"],
    ("Chevrolet", "SUV"): ["Equinox", "Tahoe"],
    ("BMW", "Sedan"): ["3 Series", "5 Series"],
    ("BMW", "SUV"): ["X3", "X5"],
    ("Tesla", "Sedan"): ["Model 3", "Model S"],
    ("Tesla", "SUV"): ["Model Y", "Model X"],
    ("Subaru", "SUV"): ["Outback", "Forester"],
    ("Mazda", "Sedan"): ["Mazda3", "Mazda6"],
    ("Hyundai", "Sedan"): ["Elantra", "Sonata"],
    ("Kia", "SUV"): ["Sportage", "Telluride"],
    ("Jeep", "SUV"): ["Wrangler", "Grand Cherokee"],
    ("Nissan", "Sedan"): ["Sentra", "Altima"],
    ("Volkswagen", "Sedan"): ["Jetta", "Passat"],
}
MAKE_PREMIUM = {
    "Honda": 0.00, "Toyota": 0.05, "Ford": -0.05, "Chevrolet": -0.05,
    "BMW": 0.30, "Tesla": 0.40, "Subaru": 0.05, "Mazda": -0.02,
    "Hyundai": -0.10, "Kia": -0.10, "Jeep": 0.10, "Nissan": -0.05,
    "Volkswagen": -0.05,
}
BODY_PREMIUM = {"Sedan": 0.0, "SUV": 0.15, "Truck": 0.20}

VHR_FLAGS_POOL = [
    "NO_SALVAGE_TITLE", "NO_FRAME_DAMAGE", "NO_FLOOD_WATER_DAMAGE",
    "NO_ACCIDENTS_REPORTED", "NO_ONE_OWNER",
]
NEGATIVE_FLAGS = {
    "SALVAGE_TITLE", "FRAME_DAMAGE", "FLOOD_WATER_DAMAGE",
    "ACCIDENTS_REPORTED", "PRIOR_USE_LEASE",
}


@dataclass
class CarSpec:
    car_id: str
    year: int
    make: str
    model: str
    body: str
    mileage: int
    true_condition: float
    true_value: float
    seller_floor: float
    seller_ceiling: float
    true_vhr_flags: list[str] = field(default_factory=list)


def _hedonic_log_price(year: int, miles: int, cond: float, make: str, body: str) -> float:
    return (
        9.7
        + 0.07 * (year - 2020)
        - 0.18 * math.log(miles + 1) / math.log(100000)
        + 0.10 * (cond - 3.0)
        + MAKE_PREMIUM.get(make, 0.0)
        + BODY_PREMIUM.get(body, 0.0)
    )


def _draw_make_body(rng: random.Random) -> tuple[str, str]:
    total = sum(w for _, _, w in MAKE_BODY_PRIOR)
    target = rng.random() * total
    acc = 0.0
    for make, body, w in MAKE_BODY_PRIOR:
        acc += w
        if target <= acc:
            return make, body
    return MAKE_BODY_PRIOR[-1][0], MAKE_BODY_PRIOR[-1][1]


def _draw_vhr_flags(rng: random.Random) -> list[str]:
    flags = []
    for pos, neg in [
        ("NO_SALVAGE_TITLE", "SALVAGE_TITLE"),
        ("NO_FRAME_DAMAGE", "FRAME_DAMAGE"),
        ("NO_FLOOD_WATER_DAMAGE", "FLOOD_WATER_DAMAGE"),
        ("NO_ACCIDENTS_REPORTED", "ACCIDENTS_REPORTED"),
        ("NO_ONE_OWNER", "PRIOR_USE_LEASE"),
    ]:
        flags.append(pos if rng.random() > 0.15 else neg)
    return flags


def generate(seed: int, n: int) -> list[CarSpec]:
    """Deterministic per seed. Returns n CarSpec with ground-truth values."""
    rng = random.Random(seed)
    out: list[CarSpec] = []
    for i in range(n):
        make, body = _draw_make_body(rng)
        model = rng.choice(MODELS_PER_MAKE_BODY[(make, body)])
        year = max(2010, min(2026, int(round(rng.gauss(2019, 3)))))
        median_miles = max(5000, int(20000 * (2026 - year) + rng.gauss(0, 15000)))
        miles = max(0, min(250000, median_miles))
        true_condition = max(1.0, min(5.0, rng.gauss(3.2, 0.7)))
        log_p = _hedonic_log_price(year, miles, true_condition, make, body) + rng.gauss(0, 0.07)
        true_value = float(math.exp(log_p))
        seller_floor = true_value * (0.9 + rng.gauss(0, 0.02))
        seller_ceiling = true_value * (1.1 + rng.gauss(0, 0.02))
        # Clip to guarantee floor < true_value < ceiling regardless of gauss noise
        seller_floor = min(seller_floor, true_value * 0.99)
        seller_ceiling = max(seller_ceiling, true_value * 1.01)
        flags = _draw_vhr_flags(rng)
        out.append(CarSpec(
            car_id=f"C_{i+1:04d}",
            year=year, make=make, model=model, body=body, mileage=miles,
            true_condition=true_condition, true_value=true_value,
            seller_floor=seller_floor, seller_ceiling=seller_ceiling,
            true_vhr_flags=flags,
        ))
    return out
