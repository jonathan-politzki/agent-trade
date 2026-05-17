"""E3 small — delegation factorial on colleague's original persona set.

Uses ONLY the 4+4 original personas and 3 cars spanning the severity range.
4 cells (H-H / H-A / A-H / A-A) x 4 sellers x 4 buyers x 3 cars x 1 seed = 192 sessions.

Routes through Google Vertex AI (Gemini 2.5 Flash Lite) for both sides.

Usage:
    # Dry-run (default): print sweep summary, do nothing
    python -m scripts.run_e3_small

    # Live run (requires gcloud ADC + GOOGLE_CLOUD_PROJECT in env)
    python -m scripts.run_e3_small --run

Environment expected for --run:
    GOOGLE_CLOUD_PROJECT=<project-id>
    GOOGLE_CLOUD_LOCATION=us-central1  (optional; default us-central1)
    GOOGLE_GENAI_USE_VERTEXAI=true     (optional; auto-detected if project set)
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from pathlib import Path

from used_car_salesman.config import CARS_DIR, GEMINI_FLASH_LITE
from used_car_salesman.orchestrator import build_sessions, run_sweep


SWEEP_ID = "e3_small"

SELLERS = ["honest", "pragmatic", "pushy", "slimy"]
BUYERS = ["grandma", "casual", "engineer", "mechanic"]
CARS = ["prius_2018", "altima_2017", "tahoe_2016"]
CELLS = [(False, False), (False, True), (True, False), (True, True)]
SEEDS = [0]

MODEL = GEMINI_FLASH_LITE


def build():
    sessions = []
    for sa, ba in CELLS:
        block = build_sessions(
            car_ids=CARS,
            seller_persona_ids=SELLERS,
            buyer_persona_ids=BUYERS,
            seeds=SEEDS,
            seller_models=[MODEL],
            buyer_models=[MODEL],
            buyer_options_narrowed=True,
            max_turns=22,
            inspection_cost=150.0,
        )
        block = [replace(cfg, seller_is_agent=sa, buyer_is_agent=ba) for cfg in block]
        sessions.extend(block)
    return sessions


def preflight() -> bool:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("ERROR: GOOGLE_CLOUD_PROJECT is not set.", file=sys.stderr)
        print("       Run: export GOOGLE_CLOUD_PROJECT=vertex-clawloop-daniel", file=sys.stderr)
        return False
    print(f"OK: GOOGLE_CLOUD_PROJECT = {project}")
    loc = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    print(f"OK: GOOGLE_CLOUD_LOCATION = {loc}")

    # Try to instantiate a Vertex client + list a model to confirm ADC works.
    try:
        from google import genai
        client = genai.Client(vertexai=True, project=project, location=loc)
        # Make a tiny no-op generate call to validate auth + model availability.
        resp = client.models.generate_content(
            model=MODEL,
            contents="ping",
            config={"max_output_tokens": 1},
        )
        print(f"OK: Vertex generated content (ping) — model {MODEL} reachable")
        return True
    except Exception as e:
        print(f"ERROR: Vertex auth/model check failed: {e}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--skip-preflight", action="store_true")
    args = ap.parse_args()

    sessions = build()
    cells_pretty = ["H-H", "H-A", "A-H", "A-A"]
    print(f"Sweep '{SWEEP_ID}': {len(sessions)} sessions")
    print(f"  sellers ({len(SELLERS)}): {SELLERS}")
    print(f"  buyers  ({len(BUYERS)}): {BUYERS}")
    print(f"  cars    ({len(CARS)}): {CARS}")
    print(f"  cells   ({len(CELLS)}): {cells_pretty}")
    print(f"  model: {MODEL} on both sides (via Vertex AI)")
    print(f"  max_turns: 22")

    if not args.run:
        print("\n[dry-run] pass --run to execute. Expected runtime: ~30-90 min on Vertex.")
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
