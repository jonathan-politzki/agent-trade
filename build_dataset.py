"""CLI: generate the synthetic car fleet from cars/archetypes.json.

  python3 build_dataset.py                     # uses cars/archetypes.json -> cars/generated/fleet.json
  python3 build_dataset.py --archetypes path   # custom input
  python3 build_dataset.py --out path          # custom output
  python3 build_dataset.py --limit 3           # generate just the first N (for smoke-testing)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic

from used_car_salesman.dataset import generate_fleet, load_archetypes
from used_car_salesman.car import save_fleet
from used_car_salesman.config import CARS_DIR, OPUS


def main() -> None:
    load_dotenv(override=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--archetypes", default=str(CARS_DIR / "archetypes.json"))
    ap.add_argument("--out", default=str(CARS_DIR / "generated" / "fleet.json"))
    ap.add_argument("--model", default=OPUS)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    archetypes = load_archetypes(Path(args.archetypes))
    if args.limit:
        archetypes = archetypes[:args.limit]
    print(f"Generating {len(archetypes)} cars with model={args.model}...")
    client = Anthropic()
    fleet = generate_fleet(client, archetypes, model=args.model)
    out = Path(args.out)
    save_fleet(fleet, out)
    print(f"\nSaved fleet ({len(fleet)} cars) to {out}")


if __name__ == "__main__":
    main()
