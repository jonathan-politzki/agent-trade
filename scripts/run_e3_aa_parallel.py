"""Run the 48 A-A sessions in parallel via ThreadPoolExecutor.

Appends results to the existing sweeps/e3_small/results.jsonl (which
already contains H-H rows from a prior serial run).

Usage:
    GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json \\
    GOOGLE_CLOUD_PROJECT=vertex-clawloop-daniel \\
    python -m scripts.run_e3_aa_parallel --run --workers 8
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, replace
from pathlib import Path

from used_car_salesman.car import load_fleet
from used_car_salesman.config import CARS_DIR, GEMINI_FLASH_LITE, SWEEPS_DIR
from used_car_salesman.orchestrator import build_sessions
from used_car_salesman.personas import load_persona_by_id
from used_car_salesman.session import run_session


SWEEP_ID = "e3_small"
SELLERS = ["honest", "pragmatic", "pushy", "slimy"]
BUYERS = ["grandma", "casual", "engineer", "mechanic"]
CARS = ["prius_2018", "altima_2017", "tahoe_2016"]
MODEL = GEMINI_FLASH_LITE


def build_aa_sessions():
    block = build_sessions(
        car_ids=CARS,
        seller_persona_ids=SELLERS,
        buyer_persona_ids=BUYERS,
        seeds=[0],
        seller_models=[MODEL],
        buyer_models=[MODEL],
        buyer_options_narrowed=True,
        max_turns=22,
        inspection_cost=150.0,
    )
    return [replace(cfg, seller_is_agent=True, buyer_is_agent=True) for cfg in block]


def run_one(cfg, fleet, sweep_dir, log_lock, results_path):
    """One session in a worker thread. Appends row to results.jsonl atomically."""
    t0 = time.time()
    try:
        car = fleet[cfg.car_id]
        seller = load_persona_by_id(cfg.seller_persona_id, "seller")
        buyer = load_persona_by_id(cfg.buyer_persona_id, "buyer")
        result = run_session(None, car, seller, buyer, cfg, sweep_dir)
        row = result.to_row()
        with log_lock:
            with results_path.open("a") as f:
                f.write(json.dumps(row, default=str) + "\n")
        return {"ok": True, "session_id": result.session_id, "outcome": result.outcome,
                "premium": result.premium_over_true, "elapsed": time.time() - t0}
    except Exception as e:
        return {"ok": False, "error": str(e), "cfg": asdict(cfg), "elapsed": time.time() - t0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    sessions = build_aa_sessions()
    print(f"A-A parallel sweep: {len(sessions)} sessions, {args.workers} workers")
    if not args.run:
        print("[dry-run] pass --run to execute")
        return

    sweep_dir = SWEEPS_DIR / SWEEP_ID
    sweep_dir.mkdir(parents=True, exist_ok=True)
    results_path = sweep_dir / "results.jsonl"
    # IMPORTANT: do NOT wipe results.jsonl — we are appending to existing H-H rows.
    fleet = load_fleet(CARS_DIR / "generated" / "fleet.json")
    log_lock = threading.Lock()

    done = 0
    errs = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(run_one, c, fleet, sweep_dir, log_lock, results_path): c
                   for c in sessions}
        for fut in as_completed(futures):
            res = fut.result()
            done += 1
            if res.get("ok"):
                p = res.get("premium")
                p_s = f"{p:+.1%}" if p is not None else "—"
                print(f"[{done:>2}/{len(sessions)}] {res['session_id']:<70} "
                      f"out={res.get('outcome'):<14} prem={p_s:>7} ({res['elapsed']:.1f}s)",
                      flush=True)
            else:
                errs += 1
                print(f"[{done:>2}/{len(sessions)}] ERROR: {res.get('error')[:120]}", flush=True)

    elapsed = time.time() - t0
    print(f"\nA-A sweep complete: {done} sessions in {elapsed:.0f}s "
          f"({elapsed/max(1,done):.1f}s/session avg, {errs} errors)")
    print(f"Results appended to {results_path}")


if __name__ == "__main__":
    main()
