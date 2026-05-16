"""Post-hoc analysis: replicate the headline statistics from the appendix.

For a single run (or multiple), compute:
  - Sale rate, mean price, total volume.
  - Opus vs Haiku splits when the run is mixed.
  - Within-pairing buyer/seller price effects (closest analog to the paper's
    joint item fixed-effects model — but without enough data to be meaningful,
    this is just illustrative).
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path


def load_run(run_dir: Path) -> dict:
    summary = json.loads((run_dir / "summary.json").read_text())
    assignment = json.loads((run_dir / "assignment.json").read_text())
    summary["models"] = assignment["models"]
    return summary


def analyze_run(run_dir: Path) -> dict:
    s = load_run(run_dir)
    deals = s["deals"]
    models = s["models"]

    by_seller_model: dict[str, list[float]] = defaultdict(list)
    by_buyer_model: dict[str, list[float]] = defaultdict(list)
    matchups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for d in deals:
        sm = models.get(d["seller"], "unknown").split("-")[1]
        bm = models.get(d["buyer"], "unknown").split("-")[1]
        by_seller_model[sm].append(d["price"])
        by_buyer_model[bm].append(d["price"])
        matchups[(sm, bm)].append(d["price"])

    def stats(xs: list[float]) -> dict:
        if not xs:
            return {"n": 0}
        return {
            "n": len(xs),
            "mean": round(statistics.mean(xs), 2),
            "median": round(statistics.median(xs), 2),
            "total": round(sum(xs), 2),
        }

    return {
        "run": s["run"],
        "mode": s["mode"],
        "n_deals": s["n_deals"],
        "total_value": s["total_value"],
        "by_seller_model": {k: stats(v) for k, v in by_seller_model.items()},
        "by_buyer_model": {k: stats(v) for k, v in by_buyer_model.items()},
        "matchups": {f"{sm}_seller_x_{bm}_buyer": stats(v) for (sm, bm), v in matchups.items()},
    }


def pretty_print(report: dict) -> None:
    print(f"\n=== {report['run']} ({report['mode']}) ===")
    print(f"Deals: {report['n_deals']}   Total value: ${report['total_value']:.2f}")
    print("\nBy seller model:")
    for k, v in report["by_seller_model"].items():
        print(f"  {k:>5}: {v}")
    print("\nBy buyer model:")
    for k, v in report["by_buyer_model"].items():
        print(f"  {k:>5}: {v}")
    print("\nBy matchup (seller × buyer):")
    for k, v in report["matchups"].items():
        print(f"  {k:>32}: {v}")


def analyze_dir(runs_root: Path) -> list[dict]:
    reports = []
    for child in sorted(runs_root.iterdir()):
        if (child / "summary.json").exists():
            reports.append(analyze_run(child))
    return reports
