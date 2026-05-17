"""E3 — Delegation experiment: H-H vs H-A vs A-H vs A-A.

Holding car/persona/seed constant across the four cells isolates the
delegation channel (does inserting agents in the middle change outcomes?).

Two sizes:
  --pilot (default): 2 buyers x 2 sellers x 2 cars x 4 cells = 32 sessions
  --full           : 6 buyers x 6 sellers x 3 cars x 4 cells = 432 sessions

Pilot covers ~$0.25 at Haiku rates and validates the pipeline.
Full produces presentation-grade numbers (~$2-5).
"""
from __future__ import annotations

import argparse
from dataclasses import replace

from used_car_salesman.config import SessionConfig, CARS_DIR, HAIKU
from used_car_salesman.orchestrator import build_sessions, run_sweep


SWEEP_ID = "e3_delegation"

PILOT_BUYERS = ["maya_chen", "alex_muller"]
PILOT_SELLERS = ["honest_hanks", "sterling_premier_motors"]
PILOT_CARS = ["prius_2018", "tahoe_2016"]

FULL_BUYERS = ["maya_chen", "mike_jen_hendricks", "alex_muller",
                "casual", "engineer", "mechanic"]
FULL_SELLERS = ["honest_hanks", "sunset_auto_gallery", "sterling_premier_motors",
                 "honest", "pushy", "slimy"]
FULL_CARS = ["prius_2018", "altima_2017", "tahoe_2016"]

CELLS = [(False, False), (False, True), (True, False), (True, True)]
SEEDS = [0]


def build(buyers, sellers, cars):
    sessions = []
    for sa, ba in CELLS:
        block = build_sessions(
            car_ids=cars,
            seller_persona_ids=sellers,
            buyer_persona_ids=buyers,
            seeds=SEEDS,
            seller_models=[HAIKU],
            buyer_models=[HAIKU],
            buyer_options_narrowed=True,
            max_turns=25,
            inspection_cost=150.0,
        )
        block = [replace(cfg, seller_is_agent=sa, buyer_is_agent=ba) for cfg in block]
        sessions.extend(block)
    return sessions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="Run the full 432-session sweep (default: 32-session pilot)")
    ap.add_argument("--run", action="store_true", help="Actually execute (default: dry-run)")
    args = ap.parse_args()

    if args.full:
        buyers, sellers, cars = FULL_BUYERS, FULL_SELLERS, FULL_CARS
    else:
        buyers, sellers, cars = PILOT_BUYERS, PILOT_SELLERS, PILOT_CARS

    sessions = build(buyers, sellers, cars)
    cells = [("H-H", False, False), ("H-A", False, True), ("A-H", True, False), ("A-A", True, True)]
    print(f"Sweep '{SWEEP_ID}' ({'full' if args.full else 'pilot'}): {len(sessions)} sessions")
    print(f"  buyers ({len(buyers)}): {buyers}")
    print(f"  sellers ({len(sellers)}): {sellers}")
    print(f"  cars ({len(cars)}): {cars}")
    print(f"  cells: {[c[0] for c in cells]}")
    print(f"  models: seller={HAIKU}, buyer={HAIKU}")
    if not args.run:
        print("\n[dry-run] pass --run to execute.")
        return
    fleet_path = CARS_DIR / "generated" / "fleet.json"
    run_sweep(SWEEP_ID, fleet_path, sessions)


if __name__ == "__main__":
    main()
