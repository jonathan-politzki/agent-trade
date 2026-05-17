"""E3 small — delegation factorial on colleague's original persona set.

Uses ONLY the 4+4 original personas and 3 cars spanning the severity range.
4 cells (H-H / H-A / A-H / A-A) x 4 sellers x 4 buyers x 3 cars x 1 seed = 192 sessions.

Routes through cliproxy when ANTHROPIC_BASE_URL is set. All Haiku.

Usage:
    # Dry-run (default): print sweep summary, do nothing
    python -m scripts.run_e3_small

    # Live run (requires cliproxy on 127.0.0.1:8317 with ANTHROPIC_BASE_URL set)
    python -m scripts.run_e3_small --run

Environment expected for --run:
    ANTHROPIC_API_KEY=kuhhandel-bench-key
    ANTHROPIC_BASE_URL=http://127.0.0.1:8317
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from dataclasses import replace

from used_car_salesman.config import HAIKU, CARS_DIR
from used_car_salesman.orchestrator import build_sessions, run_sweep


SWEEP_ID = "e3_small"

# Colleague's original 4 sellers and 4 buyers (no additions from feat/karma_flagship).
SELLERS = ["honest", "pragmatic", "pushy", "slimy"]
BUYERS = ["grandma", "casual", "engineer", "mechanic"]

# 3 cars spanning severity (sorted by asking_price - true_value gap from fleet.json):
#   prius_2018    clean       gap $445
#   altima_2017   moderate    gap $2,895
#   tahoe_2016    catastrophic gap $13,200
CARS = ["prius_2018", "altima_2017", "tahoe_2016"]

# 4 delegation cells.
CELLS = [(False, False), (False, True), (True, False), (True, True)]
SEEDS = [0]


def build():
    sessions = []
    for sa, ba in CELLS:
        block = build_sessions(
            car_ids=CARS,
            seller_persona_ids=SELLERS,
            buyer_persona_ids=BUYERS,
            seeds=SEEDS,
            seller_models=[HAIKU],
            buyer_models=[HAIKU],
            buyer_options_narrowed=True,
            max_turns=22,           # match E1 convention
            inspection_cost=150.0,
        )
        block = [replace(cfg, seller_is_agent=sa, buyer_is_agent=ba) for cfg in block]
        sessions.extend(block)
    return sessions


def preflight() -> bool:
    """Check env + cliproxy reachability. Returns True if OK."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        return False
    if not base_url:
        print("WARN: ANTHROPIC_BASE_URL not set — calls will go to api.anthropic.com directly.",
              file=sys.stderr)
        print("      To use cliproxy: export ANTHROPIC_BASE_URL=http://127.0.0.1:8317",
              file=sys.stderr)
        return True
    # Verify proxy reachable.
    url = base_url.rstrip("/") + "/v1/models"
    try:
        req = urllib.request.Request(url, headers={"x-api-key": api_key})
        with urllib.request.urlopen(req, timeout=3) as resp:
            ok = resp.status == 200
            if ok:
                print(f"OK: cliproxy reachable at {base_url} (HTTP {resp.status})")
            else:
                print(f"WARN: cliproxy returned HTTP {resp.status} at {url}")
            return ok
    except Exception as e:
        print(f"ERROR: cannot reach cliproxy at {url}: {e}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="Execute the sweep (otherwise dry-run)")
    ap.add_argument("--skip-preflight", action="store_true",
                     help="Skip cliproxy reachability check (use to run against api.anthropic.com)")
    args = ap.parse_args()

    sessions = build()
    cells_pretty = ["H-H", "H-A", "A-H", "A-A"]
    print(f"Sweep '{SWEEP_ID}': {len(sessions)} sessions")
    print(f"  sellers ({len(SELLERS)}): {SELLERS}")
    print(f"  buyers  ({len(BUYERS)}): {BUYERS}")
    print(f"  cars    ({len(CARS)}): {CARS}")
    print(f"  cells   ({len(CELLS)}): {cells_pretty}")
    print(f"  model: {HAIKU} on both sides")
    print(f"  max_turns: 22")

    if not args.run:
        print("\n[dry-run] pass --run to execute. Expected runtime: ~1-2 hours via cliproxy.")
        return

    if not args.skip_preflight:
        if not preflight():
            print("\nPreflight failed. Fix env or pass --skip-preflight.", file=sys.stderr)
            sys.exit(1)

    fleet_path = CARS_DIR / "generated" / "fleet.json"
    print(f"\nLaunching sweep against fleet {fleet_path}...")
    run_sweep(SWEEP_ID, fleet_path, sessions)


if __name__ == "__main__":
    main()
