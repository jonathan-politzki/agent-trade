"""CLI: run the reputation/karma experiment as a set of arcs.

  python3 run_arcs.py --sweep-id e4_reputation \
    --buyer-models gemini-2.5-flash \
    --n-arcs-per-cell 5 --cars-per-arc 8 --workers 8

Each arc: one seller (slimy + flash-lite) selling N cars sequentially to N
fresh casual buyers. Treatment = reputation visible to next buyer. Control =
same setup but the reputation block is stripped from the buyer's prompt.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from used_car_salesman.car import load_fleet
from used_car_salesman.arcs import build_default_arcs, run_arcs
from used_car_salesman.config import SWEEPS_DIR, CARS_DIR


def main() -> None:
    load_dotenv(override=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep-id", required=True)
    ap.add_argument("--fleet", default=str(CARS_DIR / "generated" / "fleet.json"))
    ap.add_argument("--seller-persona", default="slimy")
    ap.add_argument("--buyer-persona", default="casual")
    ap.add_argument("--seller-model", default="gemini-2.5-flash-lite")
    ap.add_argument("--buyer-models", default="gemini-2.5-flash",
                    help="Comma-separated buyer models to test. Each gets full treatment×seed coverage.")
    ap.add_argument("--n-arcs-per-cell", type=int, default=5)
    ap.add_argument("--cars-per-arc", type=int, default=8)
    ap.add_argument("--base-seed", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    fleet = load_fleet(Path(args.fleet))
    car_ids = list(fleet.keys())
    buyer_models = [b.strip() for b in args.buyer_models.split(",") if b.strip()]

    arcs = build_default_arcs(
        fleet_car_ids=car_ids,
        seller_persona=args.seller_persona,
        buyer_persona=args.buyer_persona,
        seller_model=args.seller_model,
        buyer_models=buyer_models,
        n_arcs_per_cell=args.n_arcs_per_cell,
        cars_per_arc=args.cars_per_arc,
        base_seed=args.base_seed,
    )

    out = run_arcs(args.sweep_id, Path(args.fleet), arcs, out_root=SWEEPS_DIR, workers=args.workers)
    print(f"Trades JSONL: {out}")


if __name__ == "__main__":
    main()
