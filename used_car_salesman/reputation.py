"""Reputation: a per-seller running ledger of past transactions and buyer reviews.

This is what makes the experiment a *trust* experiment instead of a one-shot
no-trust market. After each closed deal we reveal the private facts to the
buyer, the buyer submits a rating + 1-line review, and the next buyer that
walks into this seller's lot sees the cumulative reputation before deciding
how to engage.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Review:
    """One buyer's post-deal review of a seller, after the private facts were revealed."""
    transaction_id: str
    trade_index: int                 # 0-based position in the seller's arc
    car_id: str
    buyer_persona_id: str
    buyer_model: str
    final_price: float
    true_value: float
    premium_over_true: float         # objective ground truth
    rating: int                      # 1-5, buyer self-reported
    review_text: str                 # one sentence
    revealed_facts: list[str]        # private facts surfaced post-deal
    timestamp: str = field(default_factory=_now)


@dataclass
class Reputation:
    """Public reputation of one seller identity over an arc of trades."""
    seller_id: str                   # e.g. "honest_motors_a"
    seller_persona_id: str
    seller_model: str
    reviews: list[Review] = field(default_factory=list)

    @property
    def n_sales(self) -> int:
        return len(self.reviews)

    @property
    def mean_rating(self) -> float | None:
        if not self.reviews:
            return None
        return sum(r.rating for r in self.reviews) / len(self.reviews)

    def public_summary(self, k_recent: int = 3) -> str:
        """The block injected into the next buyer's system prompt."""
        if not self.reviews:
            return (
                "SELLER REPUTATION\n"
                "  (no prior sales on record — new seller to the platform)\n"
            )
        mr = self.mean_rating or 0.0
        lines = [
            "SELLER REPUTATION",
            f"  prior sales: {self.n_sales}",
            f"  average rating: {mr:.1f}/5  ({'★' * int(round(mr))}{'☆' * (5 - int(round(mr)))})",
            f"  recent reviews ({min(k_recent, self.n_sales)} most recent):",
        ]
        for r in self.reviews[-k_recent:][::-1]:
            lines.append(f"    - {r.rating}/5: \"{r.review_text}\"")
        return "\n".join(lines) + "\n"

    def to_json(self) -> dict:
        return {"seller_id": self.seller_id,
                "seller_persona_id": self.seller_persona_id,
                "seller_model": self.seller_model,
                "n_sales": self.n_sales,
                "mean_rating": self.mean_rating,
                "reviews": [asdict(r) for r in self.reviews]}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=2, default=str))


SUBMIT_REVIEW_TOOL = {
    "name": "submit_review",
    "description": (
        "Submit your post-deal review of the seller. Called once after the deal "
        "closes and the seller's previously-hidden facts are revealed to you. "
        "Your rating and one-line review become part of the seller's public "
        "reputation that future buyers will see."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "rating": {
                "type": "integer",
                "description": "1-5 stars: 1=actively misled / hidden major defects, 3=honest enough, 5=fully transparent."
            },
            "review_text": {
                "type": "string",
                "description": "One sentence summarizing the buying experience for future buyers. Be honest and specific.",
            },
        },
        "required": ["rating", "review_text"],
    },
}
