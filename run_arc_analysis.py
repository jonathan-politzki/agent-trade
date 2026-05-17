"""Analyze a reputation arc sweep — premium by trade index, treatment vs control.

  python3 run_arc_analysis.py --sweep-id e4_reputation
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from used_car_salesman.config import SWEEPS_DIR


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep-id", required=True)
    ap.add_argument("--root", default=str(SWEEPS_DIR))
    args = ap.parse_args()

    sweep_dir = Path(args.root) / args.sweep_id
    rows = []
    for line in (sweep_dir / "trades.jsonl").read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))

    n = len(rows)
    deals = [r for r in rows if r["outcome"] == "deal"]
    print(f"sweep: {args.sweep_id}   trades: {n}   deals: {len(deals)}   close rate: {len(deals)/max(n,1):.1%}")
    print()

    # Aggregate by (treatment, trade_index).
    by_cell_premium: dict[tuple[bool, int], list[float]] = defaultdict(list)
    by_cell_close: dict[tuple[bool, int], list[int]] = defaultdict(list)
    by_cell_rating: dict[tuple[bool, int], list[int]] = defaultdict(list)

    for r in rows:
        key = (bool(r.get("reputation_visible")), int(r.get("trade_index", -1)))
        by_cell_close[key].append(1 if r["outcome"] == "deal" else 0)
        if r["outcome"] == "deal" and r.get("premium_over_true") is not None:
            by_cell_premium[key].append(r["premium_over_true"])
        if r.get("review") and isinstance(r["review"], dict):
            by_cell_rating[key].append(r["review"]["rating"])

    indices = sorted({k[1] for k in by_cell_close})
    print(f"{'trade':>5} {'TREATMENT (rep visible)':>28} {'CONTROL':>22}")
    print(f"{'idx':>5} {'mean prem':>10} {'close':>6} {'rate':>6}  {'mean prem':>10} {'close':>6} {'rate':>6}")
    for idx in indices:
        cells = []
        for treat in (True, False):
            prems = by_cell_premium[(treat, idx)]
            closes = by_cell_close[(treat, idx)]
            ratings = by_cell_rating[(treat, idx)]
            prem_str = f"{statistics.mean(prems):+.1%}" if prems else "    —"
            close_str = f"{sum(closes)/len(closes):.0%}" if closes else "  —"
            rating_str = f"{statistics.mean(ratings):.1f}" if ratings else "  —"
            cells.append((prem_str, close_str, rating_str, len(closes)))
        t, c = cells
        print(f"{idx:>5} {t[0]:>10} {t[1]:>6} {t[2]:>6}  {c[0]:>10} {c[1]:>6} {c[2]:>6}")

    # Per-treatment summary across all trades.
    print()
    for treat, label in [(True, "TREATMENT (rep visible)"), (False, "CONTROL (rep hidden)")]:
        all_prems = [p for (t, _), prems in by_cell_premium.items() if t == treat for p in prems]
        all_closes = [c for (t, _), cs in by_cell_close.items() if t == treat for c in cs]
        all_ratings = [r for (t, _), rs in by_cell_rating.items() if t == treat for r in rs]
        prem = statistics.mean(all_prems) if all_prems else None
        close = sum(all_closes) / len(all_closes) if all_closes else None
        rating = statistics.mean(all_ratings) if all_ratings else None
        print(f"{label}: deals={len(all_prems)}  mean prem={prem:+.1%}  close={close:.1%}  rating={rating:.2f}" if prem is not None else f"{label}: no deals")

    # Persist a CSV-friendly aggregate.
    out = {
        "by_cell": {f"{('rep' if t else 'ctrl')}_t{idx}": {
            "n": len(by_cell_close[(t, idx)]),
            "close_rate": (sum(by_cell_close[(t, idx)]) / len(by_cell_close[(t, idx)])) if by_cell_close[(t, idx)] else None,
            "mean_premium": (statistics.mean(by_cell_premium[(t, idx)]) if by_cell_premium[(t, idx)] else None),
            "mean_rating": (statistics.mean(by_cell_rating[(t, idx)]) if by_cell_rating[(t, idx)] else None),
        } for t, idx in by_cell_close},
    }
    (sweep_dir / "arc_summary.json").write_text(json.dumps(out, indent=2))
    print(f"\nArc summary written to {sweep_dir / 'arc_summary.json'}")


if __name__ == "__main__":
    main()
