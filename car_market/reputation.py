"""Beta-Bernoulli reputation per seller with exponential decay."""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_COND_GAP = 2.0


def honesty_from_gap(gap: float) -> float:
    """Map |listing_cond - true_cond| → honesty in [0, 1]."""
    return max(0.0, min(1.0, 1.0 - abs(gap) / MAX_COND_GAP))


@dataclass
class BetaReputation:
    seller_id: str
    alpha: float = 2.0
    beta: float = 2.0
    review_count: int = 0
    decay: float = 0.97
    excerpts: list[str] = field(default_factory=list)

    def mean_rating(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    def stars(self) -> float:
        """Mean rating mapped to 1.0..5.0 stars."""
        return 1.0 + 4.0 * self.mean_rating()


def update_on_deal(
    rep: BetaReputation,
    listing_cond: float,
    true_cond: float,
    excerpt_factory=None,
) -> None:
    h = honesty_from_gap(listing_cond - true_cond)
    rep.alpha = rep.decay * rep.alpha + h
    rep.beta = rep.decay * rep.beta + (1.0 - h)
    rep.review_count += 1
    if h < 0.5 and excerpt_factory is not None:
        rep.excerpts.append(excerpt_factory(listing_cond=listing_cond, true_cond=true_cond))
    if len(rep.excerpts) > 5:
        rep.excerpts = rep.excerpts[-5:]
