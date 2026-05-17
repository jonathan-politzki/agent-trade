"""Sweep across (seller × buyer × car × seed × toggles) and write a flat
results table for downstream analysis.

Output layout:
  sweeps/<sweep_id>/
    sweep_config.json
    results.jsonl                       (one row per session)
    <session_id>/transcript.jsonl
    <session_id>/session.json
    <session_id>/seller_system.txt
    <session_id>/buyer_system.txt
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from itertools import product
from pathlib import Path
from typing import Iterable

from .car import Car, load_fleet
from .config import SessionConfig, SWEEPS_DIR, DEFAULT_SELLER_MODEL, DEFAULT_BUYER_MODEL
from .personas import load_persona_by_id
from .session import run_session


def build_sessions(
    car_ids: list[str],
    seller_persona_ids: list[str],
    buyer_persona_ids: list[str],
    *,
    seeds: list[int] = [0],
    hacking_tactics: list[str | None] = [None],
    seller_knows_buyer_options: list[bool] = [False],
    seller_models: list[str] = [DEFAULT_SELLER_MODEL],
    buyer_models: list[str] = [DEFAULT_BUYER_MODEL],
    buyer_options_narrowed: bool = True,
    max_turns: int = 25,
    inspection_cost: float = 150.0,
) -> list[SessionConfig]:
    sessions = []
    for (car_id, seller, buyer, seed, tactic, skb, sm, bm) in product(
        car_ids, seller_persona_ids, buyer_persona_ids,
        seeds, hacking_tactics, seller_knows_buyer_options,
        seller_models, buyer_models,
    ):
        sessions.append(SessionConfig(
            car_id=car_id,
            seller_persona_id=seller,
            buyer_persona_id=buyer,
            seller_model=sm,
            buyer_model=bm,
            buyer_options_narrowed=buyer_options_narrowed,
            seller_knows_buyer=skb,
            hacking_tactic=tactic,
            max_turns=max_turns,
            inspection_cost=inspection_cost,
            seed=seed,
        ))
    return sessions


def _run_one(cfg: SessionConfig, fleet: dict, sweep_dir: Path):
    """Pure session worker — created per task. Caller threads invoke this."""
    car = fleet[cfg.car_id]
    seller = load_persona_by_id(cfg.seller_persona_id, "seller")
    buyer = load_persona_by_id(cfg.buyer_persona_id, "buyer")
    return run_session(None, car, seller, buyer, cfg, sweep_dir)


def run_sweep(
    sweep_id: str,
    fleet_path: Path,
    sessions: Iterable[SessionConfig],
    out_root: Path = SWEEPS_DIR,
    *,
    workers: int = 1,
) -> Path:
    sweep_dir = out_root / sweep_id
    sweep_dir.mkdir(parents=True, exist_ok=True)
    fleet = load_fleet(fleet_path)
    results_path = sweep_dir / "results.jsonl"
    results_path.write_text("")

    sessions = list(sessions)
    cfg_dump = {
        "sweep_id": sweep_id,
        "fleet_path": str(fleet_path),
        "n_sessions": len(sessions),
        "workers": workers,
        "sessions": [asdict(s) for s in sessions],
    }
    (sweep_dir / "sweep_config.json").write_text(json.dumps(cfg_dump, indent=2))

    write_lock = threading.Lock()
    done_count = {"n": 0}

    def write_row(row: dict) -> None:
        with write_lock:
            try:
                results_path.parent.mkdir(parents=True, exist_ok=True)
                with results_path.open("a") as f:
                    f.write(json.dumps(row, default=str) + "\n")
            except FileNotFoundError:
                results_path.parent.mkdir(parents=True, exist_ok=True)
                with results_path.open("a") as f:
                    f.write(json.dumps(row, default=str) + "\n")
            done_count["n"] += 1

    print(f"\n=== sweep {sweep_id}: {len(sessions)} sessions, {workers} workers ===")

    if workers <= 1:
        for i, cfg in enumerate(sessions, 1):
            tag = f"[{i:>3}/{len(sessions)}]"
            print(f"{tag} {cfg.car_id} | {cfg.seller_persona_id} -> {cfg.buyer_persona_id} | "
                  f"sm={cfg.seller_model} bm={cfg.buyer_model} | seed={cfg.seed}")
            t0 = time.time()
            try:
                result = _run_one(cfg, fleet, sweep_dir)
                write_row(result.to_row())
                price = f"${result.final_price:,.0f}" if result.final_price else "—"
                prem = f"{result.premium_over_true:+.1%}" if result.premium_over_true is not None else "—"
                print(f"        outcome={result.outcome} price={price} premium={prem} "
                      f"turns={result.n_turns} insp={result.n_inspections} ({time.time()-t0:.0f}s)")
            except Exception as e:
                print(f"        ERROR: {e}")
                write_row({"error": str(e), "cfg": asdict(cfg)})
        print(f"\nSweep complete. Results at {results_path}")
        return results_path

    # Concurrent path.
    total = len(sessions)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_run_one, cfg, fleet, sweep_dir): cfg for cfg in sessions}
        for fut in as_completed(futures):
            cfg = futures[fut]
            try:
                result = fut.result()
                row = result.to_row()
                write_row(row)
                price = f"${result.final_price:,.0f}" if result.final_price else "—"
                prem = f"{result.premium_over_true:+.1%}" if result.premium_over_true is not None else "—"
                print(f"[{done_count['n']:>3}/{total}] {cfg.car_id} | "
                      f"{cfg.seller_persona_id}->{cfg.buyer_persona_id} | "
                      f"sm={cfg.seller_model} bm={cfg.buyer_model} seed={cfg.seed} | "
                      f"{result.outcome} price={price} premium={prem} turns={result.n_turns}",
                      flush=True)
            except Exception as e:
                write_row({"error": str(e), "cfg": asdict(cfg)})
                print(f"[{done_count['n']:>3}/{total}] ERROR on {cfg.car_id} {cfg.seller_persona_id}->{cfg.buyer_persona_id}: {e}", flush=True)

    print(f"\nSweep complete. Results at {results_path}")
    return results_path
