"""Car schema. This is the contract between the dataset layer and the
session layer — swap `dataset.py` for a real-world dataset adapter and as
long as it emits objects matching this shape, everything else keeps working.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


# Focus areas a buyer can pay to inspect. Each private fact carries a
# focus_area tag so inspections reveal a coherent subset.
FOCUS_AREAS = ("engine", "transmission", "body", "history", "title", "interior")


@dataclass
class PrivateFact:
    """One piece of information the seller knows that the buyer doesn't."""
    focus_area: str            # one of FOCUS_AREAS
    summary: str               # short label, e.g. "rear bumper repainted after parking-lot scrape"
    severity: int              # 1 (cosmetic) to 5 (major safety)
    price_impact_usd: float    # negative number: how much it knocks off true_value


@dataclass
class Car:
    car_id: str
    year: int
    make: str
    model: str
    trim: str
    odometer_miles: int                 # what the dashboard reads — may not be the real mileage
    exterior_condition: str             # "excellent" | "good" | "fair" | "rough"
    asking_price: float                 # what's on the ad
    dealer_pitch: str                   # the listing's marketing blurb

    # Hidden side: only the seller agent sees these.
    private_facts: list[PrivateFact] = field(default_factory=list)
    real_mileage: int | None = None     # if different from odometer (rolled-back), this is real

    # Ground-truth valuations.
    public_fair_value: float = 0.0      # value if the public side is the whole truth
    true_value: float = 0.0             # value given full disclosure
    reasoning: str = ""                 # Claude's chain-of-reasoning during generation, for audit

    def public_view(self) -> dict:
        """What the buyer agent sees (no private facts, no true_value)."""
        return {
            "car_id": self.car_id,
            "year": self.year,
            "make": self.make,
            "model": self.model,
            "trim": self.trim,
            "odometer_miles": self.odometer_miles,
            "exterior_condition": self.exterior_condition,
            "asking_price": self.asking_price,
            "dealer_pitch": self.dealer_pitch,
        }

    def seller_view(self) -> dict:
        """What the seller agent sees — everything except the buyer's regret-side."""
        return {
            **self.public_view(),
            "real_mileage": self.real_mileage if self.real_mileage is not None else self.odometer_miles,
            "private_facts": [asdict(f) for f in self.private_facts],
            "public_fair_value": self.public_fair_value,
            "true_value": self.true_value,
        }

    def inspection_findings(self, focus_area: str) -> list[PrivateFact]:
        return [f for f in self.private_facts if f.focus_area == focus_area]

    def to_json(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_json(cls, data: dict) -> "Car":
        facts = [PrivateFact(**f) for f in data.get("private_facts", [])]
        return cls(
            car_id=data["car_id"],
            year=data["year"],
            make=data["make"],
            model=data["model"],
            trim=data["trim"],
            odometer_miles=data["odometer_miles"],
            exterior_condition=data["exterior_condition"],
            asking_price=data["asking_price"],
            dealer_pitch=data["dealer_pitch"],
            private_facts=facts,
            real_mileage=data.get("real_mileage"),
            public_fair_value=data.get("public_fair_value", 0.0),
            true_value=data.get("true_value", 0.0),
            reasoning=data.get("reasoning", ""),
        )


def load_fleet(path: Path) -> dict[str, Car]:
    data = json.loads(Path(path).read_text())
    return {c["car_id"]: Car.from_json(c) for c in data}


def save_fleet(cars: list[Car], path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps([c.to_json() for c in cars], indent=2))
