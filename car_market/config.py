"""Run-time config for car_market scenarios."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class S3Config:
    seed: int = 0
    k_sellers: int = 20
    inventory_per_seller: tuple[int, int] = (3, 8)
    m_buyers: int = 150
    T: int = 400
    max_neg_turns: int = 6
    max_concurrent_per_seller: int = 5
    reputation_gamma: float = 0.5     # 0.0 = hidden mode
    mode: str = "fast"                # fast | llm | replay
    llm_model: str = "anthropic/claude-haiku-4-5"
    out_dir: str = "runs"
    cars_source: str = "curated"     # "generator" | "curated"
    sellers_source: str = "curated"  # "anonymous" | "curated"
