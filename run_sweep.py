"""CLI: run a sweep across the full (or restricted) experiment grid.

  python3 run_sweep.py --sweep-id v1                                    # full 4x4xN_cars, baseline (no tactics, no seller_knows_buyer)
  python3 run_sweep.py --sweep-id hacking --tactics anchor_high,false_urgency,phantom_other_buyer
  python3 run_sweep.py --sweep-id skb --seller-knows-buyer
  python3 run_sweep.py --sweep-id smoke --cars camry_2018 --sellers slimy --buyers grandma,mechanic
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from used_car_salesman.car import load_fleet
from used_car_salesman.config import (
    SWEEPS_DIR, CARS_DIR, DEFAULT_SELLER_MODEL, DEFAULT_BUYER_MODEL, DEFAULT_MAX_TURNS,
)
from used_car_salesman.orchestrator import build_sessions, run_sweep


def _csv(arg: str | None, default: list[str] | None = None) -> list[str]:
    if not arg:
        return default or []
    return [x.strip() for x in arg.split(",") if x.strip()]


def main() -> None:
    load_dotenv(override=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep-id", required=True)
    ap.add_argument("--fleet", default=str(CARS_DIR / "generated" / "fleet.json"))
    ap.add_argument("--cars", default=None, help="Comma-separated car_ids. Default: all in fleet.")
    ap.add_argument("--sellers", default="honest,pragmatic,pushy,slimy")
    ap.add_argument("--buyers", default="grandma,casual,engineer,mechanic")
    ap.add_argument("--tactics", default=None, help="Comma-separated tactic ids; or 'none' for baseline only.")
    ap.add_argument("--include-baseline", action="store_true", help="When --tactics is set, also include the no-tactic baseline.")
    ap.add_argument("--seller-knows-buyer", action="store_true")
    ap.add_argument("--also-without-skb", action="store_true", help="Run BOTH with and without seller_knows_buyer.")
    ap.add_argument("--seller-models", default=DEFAULT_SELLER_MODEL)
    ap.add_argument("--buyer-models", default=DEFAULT_BUYER_MODEL)
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    args = ap.parse_args()

    fleet = load_fleet(Path(args.fleet))
    all_car_ids = list(fleet.keys())
    car_ids = _csv(args.cars, all_car_ids)
    sellers = _csv(args.sellers)
    buyers = _csv(args.buyers)
    seeds = [int(x) for x in _csv(args.seeds, ["0"])]

    if args.tactics:
        tactics = [None] if args.include_baseline else []
        tactics += [None if t == "none" else t for t in _csv(args.tactics)]
    else:
        tactics = [None]

    if args.seller_knows_buyer and args.also_without_skb:
        skb_opts = [False, True]
    elif args.seller_knows_buyer:
        skb_opts = [True]
    else:
        skb_opts = [False]

    sessions = build_sessions(
        car_ids=car_ids,
        seller_persona_ids=sellers,
        buyer_persona_ids=buyers,
        seeds=seeds,
        hacking_tactics=tactics,
        seller_knows_buyer_options=skb_opts,
        seller_models=_csv(args.seller_models),
        buyer_models=_csv(args.buyer_models),
        max_turns=args.max_turns,
    )

    out_path = run_sweep(args.sweep_id, Path(args.fleet), sessions, out_root=SWEEPS_DIR)
    print(f"Results JSONL: {out_path}")


if __name__ == "__main__":
    main()
