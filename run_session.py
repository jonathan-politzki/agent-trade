"""CLI: run a single buyer-seller session for debugging / inspection.

  python3 run_session.py --car camry_2018 --seller slimy --buyer grandma
  python3 run_session.py --car f150_2015 --seller pushy --buyer mechanic --tactic phantom_other_buyer --seller-knows-buyer
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic

from used_car_salesman.car import load_fleet
from used_car_salesman.config import (
    SessionConfig, SWEEPS_DIR, CARS_DIR,
    DEFAULT_SELLER_MODEL, DEFAULT_BUYER_MODEL, DEFAULT_MAX_TURNS,
)
from used_car_salesman.personas import load_persona_by_id
from used_car_salesman.session import run_session


def main() -> None:
    load_dotenv(override=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--car", required=True)
    ap.add_argument("--seller", required=True)
    ap.add_argument("--buyer", required=True)
    ap.add_argument("--fleet", default=str(CARS_DIR / "generated" / "fleet.json"))
    ap.add_argument("--tactic", default=None)
    ap.add_argument("--seller-knows-buyer", action="store_true")
    ap.add_argument("--buyer-options-narrowed", action="store_true", default=True)
    ap.add_argument("--seller-model", default=DEFAULT_SELLER_MODEL)
    ap.add_argument("--buyer-model", default=DEFAULT_BUYER_MODEL)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    ap.add_argument("--sweep-id", default="adhoc")
    args = ap.parse_args()

    fleet = load_fleet(Path(args.fleet))
    car = fleet[args.car]
    seller = load_persona_by_id(args.seller, "seller")
    buyer = load_persona_by_id(args.buyer, "buyer")

    cfg = SessionConfig(
        car_id=args.car,
        seller_persona_id=args.seller,
        buyer_persona_id=args.buyer,
        seller_model=args.seller_model,
        buyer_model=args.buyer_model,
        buyer_options_narrowed=args.buyer_options_narrowed,
        seller_knows_buyer=args.seller_knows_buyer,
        hacking_tactic=args.tactic,
        max_turns=args.max_turns,
        seed=args.seed,
    )

    sweep_dir = SWEEPS_DIR / args.sweep_id
    sweep_dir.mkdir(parents=True, exist_ok=True)

    client = Anthropic()
    result = run_session(client, car, seller, buyer, cfg, sweep_dir)
    print()
    print(f"session_id: {result.session_id}")
    print(f"outcome: {result.outcome}")
    if result.final_price is not None:
        print(f"final price: ${result.final_price:,.2f}")
        print(f"asking price: ${result.asking_price:,.2f}")
        print(f"public fair value: ${result.public_fair_value:,.2f}")
        print(f"true value: ${result.true_value:,.2f}")
        if result.premium_over_true is not None:
            print(f"premium vs true: {result.premium_over_true:+.2%}")
        if result.premium_over_listed is not None:
            print(f"premium vs listed: {result.premium_over_listed:+.2%}")
    print(f"turns: {result.n_turns}  questions: {result.n_questions}  inspections: {result.n_inspections}")
    print(f"transcript: {result.transcript_path}")


if __name__ == "__main__":
    main()
