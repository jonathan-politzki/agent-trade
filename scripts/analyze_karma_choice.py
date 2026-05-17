"""Path A post-hoc karma-discovery analysis.

For each buyer, the existing sweep (run_flagship_karma.py) has results
against EVERY seller in the seller set. We simulate three dealer-choice
policies and ask: how much buyer welfare differs across policies?

  random          — buyer picks a seller uniformly at random. Expected
                    welfare = mean across all sellers for that buyer.
  karma-greedy    — buyer picks the highest-karma seller available.
                    Welfare = the (buyer, top-karma-seller) cell.
  karma-softmax   — buyer picks weighted by exp(beta * karma_score).
                    Welfare = sum_s p(s) * welfare(buyer, s).

In the *karma-visible* world the buyer can apply karma-greedy/softmax.
In the *karma-hidden* world the buyer is stuck with random. The welfare
delta is the value of karma as a discovery signal.

Usage:
    python -m scripts.analyze_karma_choice \\
        --results sweeps/flagship_karma/results.jsonl \\
        --personas-dir personas
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean


def load_results(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_karma_map(personas_dir: Path) -> dict[str, float]:
    """Load karma_score per seller_persona_id."""
    out: dict[str, float] = {}
    for p in (personas_dir / "sellers").glob("*.json"):
        d = json.loads(p.read_text())
        if "karma_score" in d:
            out[d["persona_id"]] = float(d["karma_score"])
    return out


def buyer_welfare(row: dict) -> float | None:
    """Buyer-side welfare proxy. Higher is better.

    A buyer's welfare from a transaction:
      - if outcome == 'deal': true_value - final_price
        (positive when buyer paid below true value; negative if overpaid)
      - if outcome in ('walk_away_buyer', 'walk_away_seller', 'timeout'):
        0 (buyer remains in market without paying — no welfare gain or loss)

    Note: this is asymmetric in the sense that the *buyer's regret about not
    transacting* isn't captured. For a richer welfare formula plug in the
    persona's reservation - true_value gap. Simple version first.
    """
    outcome = row.get("outcome")
    if outcome != "deal":
        return 0.0
    fp = row.get("final_price")
    tv = row.get("true_value")
    if fp is None or tv is None:
        return None
    return float(tv) - float(fp)


def group_by_buyer_seller(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    g: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        b = r.get("buyer_persona_id")
        s = r.get("seller_persona_id")
        if b and s:
            g[(b, s)].append(r)
    return g


def simulate_policies(
    rows: list[dict],
    karma_map: dict[str, float],
    softmax_beta: float = 3.0,
) -> dict:
    """For each buyer, simulate three dealer-choice policies on the (buyer x seller)
    welfare matrix collapsed across cars/seeds. Returns aggregate buyer-welfare
    per policy."""
    by_pair = group_by_buyer_seller(rows)
    # Collapse each (buyer, seller) cell to mean buyer_welfare across cars/seeds.
    cell_welfare: dict[tuple[str, str], float] = {}
    for (b, s), bucket in by_pair.items():
        ws = [w for w in (buyer_welfare(r) for r in bucket) if w is not None]
        cell_welfare[(b, s)] = mean(ws) if ws else 0.0

    buyers = sorted({b for (b, _) in cell_welfare})
    sellers = sorted({s for (_, s) in cell_welfare})

    per_buyer = {}
    for b in buyers:
        row_vals = []
        for s in sellers:
            if (b, s) in cell_welfare:
                row_vals.append((s, cell_welfare[(b, s)]))
        if not row_vals:
            continue
        ws = [w for _, w in row_vals]
        rand_w = mean(ws)
        # karma-greedy: pick the seller with the highest karma (NOT highest welfare —
        # that would be omniscient; we only observe karma).
        ranked_by_karma = sorted(row_vals, key=lambda x: -karma_map.get(x[0], 0.0))
        greedy_w = ranked_by_karma[0][1] if ranked_by_karma else 0.0
        # karma-softmax: weighted by exp(beta * karma)
        weights = [math.exp(softmax_beta * karma_map.get(s, 0.0)) for s, _ in row_vals]
        total = sum(weights) or 1.0
        soft_w = sum(w_val * w_wt for (_, w_val), w_wt in zip(row_vals, weights)) / total

        per_buyer[b] = {
            "random": rand_w,
            "karma_greedy": greedy_w,
            "karma_softmax": soft_w,
            "n_sellers": len(row_vals),
        }

    # Aggregate across buyers.
    if not per_buyer:
        return {"per_buyer": {}, "aggregate": {}}
    agg = {
        "random_mean": mean(d["random"] for d in per_buyer.values()),
        "karma_greedy_mean": mean(d["karma_greedy"] for d in per_buyer.values()),
        "karma_softmax_mean": mean(d["karma_softmax"] for d in per_buyer.values()),
        "n_buyers": len(per_buyer),
    }
    agg["delta_greedy_minus_random"] = agg["karma_greedy_mean"] - agg["random_mean"]
    agg["delta_softmax_minus_random"] = agg["karma_softmax_mean"] - agg["random_mean"]
    return {"per_buyer": per_buyer, "aggregate": agg}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True,
                     help="Path to sweep's results.jsonl")
    ap.add_argument("--personas-dir", default="personas",
                     help="Path to personas/ directory (contains sellers/*.json with karma_score)")
    ap.add_argument("--filter-karma-visible", choices=["both", "true", "false"], default="both",
                     help="If 'true' or 'false', only analyze rows where karma_visible matches. Default 'both' uses all rows.")
    ap.add_argument("--softmax-beta", type=float, default=3.0)
    args = ap.parse_args()

    rows = load_results(Path(args.results))
    if args.filter_karma_visible != "both":
        want = (args.filter_karma_visible == "true")
        rows = [r for r in rows if r.get("karma_visible") == want]
    karma_map = load_karma_map(Path(args.personas_dir))

    print(f"Loaded {len(rows)} session rows; karma_score known for {len(karma_map)} sellers")
    print(f"Filter karma_visible={args.filter_karma_visible}; softmax beta={args.softmax_beta}")

    result = simulate_policies(rows, karma_map, softmax_beta=args.softmax_beta)
    agg = result["aggregate"]
    if not agg:
        print("No valid rows for analysis.")
        return
    print("\n=== Aggregate buyer welfare (mean across buyers) ===")
    print(f"  random policy        : ${agg['random_mean']:>+,.0f}")
    print(f"  karma-greedy policy  : ${agg['karma_greedy_mean']:>+,.0f}")
    print(f"  karma-softmax (beta={args.softmax_beta}): ${agg['karma_softmax_mean']:>+,.0f}")
    print(f"\n  delta greedy - random  : ${agg['delta_greedy_minus_random']:>+,.0f}")
    print(f"  delta softmax - random : ${agg['delta_softmax_minus_random']:>+,.0f}")
    print(f"\n  n_buyers contributing  : {agg['n_buyers']}")

    print("\n=== Per buyer ===")
    for b, d in result["per_buyer"].items():
        print(f"  {b:<26} random=${d['random']:+,.0f}  greedy=${d['karma_greedy']:+,.0f}  "
              f"softmax=${d['karma_softmax']:+,.0f}  n_sellers={d['n_sellers']}")


if __name__ == "__main__":
    main()
