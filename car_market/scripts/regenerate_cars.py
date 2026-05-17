"""Regenerate the curated demo car set from the procedural generator.

Idempotent: same seed always produces same JSONs. Run when you want a
fresh curated pool or when generator constants change. The simulation
itself never calls generate() at runtime — it only reads these files.

Usage:
    python -m car_market.scripts.regenerate_cars [--seed N] [--n N] [--clean]
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from car_market.generator import generate, CARS_DIR


def regenerate(seed: int = 2026, n: int = 200, clean: bool = True) -> int:
    if clean:
        for old in CARS_DIR.glob("*.json"):
            old.unlink()
    cars = generate(seed=seed, n=n)
    CARS_DIR.mkdir(parents=True, exist_ok=True)
    width = max(3, len(str(n)))
    for i, c in enumerate(cars, start=1):
        path = CARS_DIR / f"C_GEN_{i:0{width}d}.json"
        # Override car_id to match the filename for clarity.
        record = {
            "car_id": f"C_GEN_{i:0{width}d}",
            "year": c.year, "make": c.make, "model": c.model, "body": c.body,
            "mileage": c.mileage,
            "true_condition": c.true_condition,
            "true_value": c.true_value,
            "seller_floor": c.seller_floor,
            "seller_ceiling": c.seller_ceiling,
            "true_vhr_flags": c.true_vhr_flags,
        }
        path.write_text(json.dumps(record, indent=2))
    return len(cars)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--no-clean", dest="clean", action="store_false",
                     help="Don't delete existing JSONs before regenerating")
    args = ap.parse_args()
    count = regenerate(seed=args.seed, n=args.n, clean=args.clean)
    print(f"wrote {count} car JSONs to {CARS_DIR}")


if __name__ == "__main__":
    main()
