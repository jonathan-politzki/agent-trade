"""Locked metric formulas (spec §9.1). The evaluator implements these
literally; figures derive from them."""
from __future__ import annotations

from typing import Iterable


def deal_welfare(price: float, true_value: float, buyer_utility: float) -> tuple[float, float, float]:
    """(buyer_surplus, seller_surplus, deal_welfare).
    Buyer surplus uses true U (oracle utility for the persona), not perceived
    U at listing claim. Seller surplus uses true_value (oracle), not the
    seller's floor estimate."""
    buyer_surplus = buyer_utility - price
    seller_surplus = price - true_value
    return buyer_surplus, seller_surplus, buyer_surplus + seller_surplus


def gini(values: Iterable[float]) -> float:
    xs = sorted(values)
    n = len(xs)
    if n == 0:
        return 0.0
    s = sum(xs)
    if s == 0:
        return 0.0
    cum = 0.0
    for i, x in enumerate(xs, start=1):
        cum += i * x
    return (2 * cum) / (n * s) - (n + 1) / n


def run_metrics(deals: list[dict], no_deal_buyers: int) -> dict:
    """Compute per-run aggregates from per-deal records."""
    if not deals:
        return {
            "total_welfare": 0.0, "mean_buyer_surplus": 0.0,
            "mean_seller_surplus": 0.0, "n_deals": 0,
            "pct_buyers_served": 0.0, "buyer_surplus_gini": 0.0,
        }
    bs_list = [d["buyer_surplus"] for d in deals]
    ss_list = [d["seller_surplus"] for d in deals]
    n_served = len({d["buyer"] for d in deals})
    n_total = n_served + no_deal_buyers
    # No-deal buyers count as buyer_surplus=0 in the average.
    return {
        "total_welfare": float(sum(d["deal_welfare"] for d in deals)),
        "mean_buyer_surplus": float(sum(bs_list) / max(1, n_total)),
        "mean_seller_surplus": float(sum(ss_list) / max(1, len(ss_list))),
        "n_deals": len(deals),
        "pct_buyers_served": n_served / max(1, n_total),
        "buyer_surplus_gini": gini(bs_list),
    }
