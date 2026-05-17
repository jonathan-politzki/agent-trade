"""Flagship experiment: does visible seller karma reduce premium-over-true?

216 sessions:
  6 buyers x 6 sellers x 3 cars x 2 karma conditions x 1 seed

Buyers (3 ours + 3 theirs):
  maya_chen, mike_jen_hendricks, alex_muller, casual, engineer, mechanic

Sellers (3 ours + 3 theirs):
  honest_hanks, sunset_auto_gallery, sterling_premier_motors,
  honest, pushy, slimy

Cars (clean / moderate / severe):
  prius_2018 (clean control), altima_2017 (severe moderate-class),
  tahoe_2016 (catastrophic).

Both sides: claude-haiku-4-5.

NOTE: this script defines the sweep config and PRINTS what it would run.
Pass --run to actually execute (LLM cost: ~$2-5 depending on rates)."""
from __future__ import annotations

import argparse
from pathlib import Path

from used_car_salesman.config import SWEEPS_DIR, CARS_DIR, HAIKU
from used_car_salesman.orchestrator import build_sessions, run_sweep


SWEEP_ID = "flagship_karma"

BUYERS = [
    "maya_chen", "mike_jen_hendricks", "alex_muller",
    "casual", "engineer", "mechanic",
]
SELLERS = [
    "honest_hanks", "sunset_auto_gallery", "sterling_premier_motors",
    "honest", "pushy", "slimy",
]
CARS = ["prius_2018", "altima_2017", "tahoe_2016"]
SEEDS = [0]
KARMA_CONDITIONS = [False, True]


def build():
    # Sessions for both karma_visible values
    sessions = []
    for karma in KARMA_CONDITIONS:
        block = build_sessions(
            car_ids=CARS,
            seller_persona_ids=SELLERS,
            buyer_persona_ids=BUYERS,
            seeds=SEEDS,
            seller_models=[HAIKU],
            buyer_models=[HAIKU],
            buyer_options_narrowed=True,
            max_turns=25,
            inspection_cost=150.0,
        )
        # build_sessions doesn't have a karma_visible param; patch each cfg.
        from dataclasses import replace
        block = [replace(cfg, karma_visible=karma) for cfg in block]
        sessions.extend(block)
    return sessions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="Actually execute the sweep (otherwise dry-run / print only)")
    args = ap.parse_args()
    sessions = build()
    print(f"Sweep '{SWEEP_ID}': {len(sessions)} sessions")
    print(f"  buyers: {BUYERS}")
    print(f"  sellers: {SELLERS}")
    print(f"  cars: {CARS}")
    print(f"  karma conditions: {KARMA_CONDITIONS}")
    print(f"  models: seller={HAIKU}, buyer={HAIKU}")
    if not args.run:
        print("\n[dry-run] pass --run to execute.")
        return
    fleet_path = CARS_DIR / "generated" / "fleet.json"
    run_sweep(SWEEP_ID, fleet_path, sessions)


if __name__ == "__main__":
    main()
