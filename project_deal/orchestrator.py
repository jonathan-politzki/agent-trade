"""Marketplace orchestrator.

Loads participant profiles, assigns models per the factorial design (all Opus,
or 50/50 Opus/Haiku), then loops through agents in a randomized order. Each
round every agent gets exactly one turn. All public events are written to a
JSONL log so the analysis script can reconstruct what happened.
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import asdict
from pathlib import Path

from anthropic import Anthropic

from .agent import Participant, run_turn
from .config import OPUS, HAIKU, RunConfig
from .marketplace import Marketplace


def load_participant(path: Path) -> dict:
    return json.loads(path.read_text())


def assign_models(names: list[str], mode: str, rng: random.Random) -> dict[str, str]:
    """mode: 'all_opus' or 'mixed' (~50/50 random Opus/Haiku, like runs B & C)."""
    if mode == "all_opus":
        return {n: OPUS for n in names}
    if mode == "mixed":
        shuffled = names[:]
        rng.shuffle(shuffled)
        half = len(shuffled) // 2
        opus = set(shuffled[:half])
        return {n: (OPUS if n in opus else HAIKU) for n in names}
    raise ValueError(f"Unknown mode: {mode}")


def run_market(
    profile_paths: list[Path],
    cfg: RunConfig,
    mode: str = "mixed",
    initial_budget: float = 100.0,
    out_dir: Path = Path("runs"),
) -> dict:
    """Execute one marketplace run end-to-end."""
    rng = random.Random(cfg.seed)
    profiles = {p.stem: load_participant(p) for p in profile_paths}
    names = list(profiles.keys())
    models = assign_models(names, mode, rng)

    run_dir = out_dir / cfg.name
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "events.jsonl"
    mp = Marketplace(cfg.name, log_path=log_path)

    participants: dict[str, Participant] = {
        name: Participant(
            name=name,
            model=models[name],
            system_prompt=profiles[name]["system_prompt"],
            budget_remaining=initial_budget,
        )
        for name in names
    }

    (run_dir / "assignment.json").write_text(json.dumps({
        "run": cfg.name, "mode": mode, "models": models,
        "initial_budget": initial_budget, "participants": names,
    }, indent=2))

    client = Anthropic()
    turn_log_path = run_dir / "turns.jsonl"
    turn_log_path.write_text("")

    print(f"\n=== Run {cfg.name} | mode={mode} | {len(names)} agents | {cfg.rounds} rounds ===")
    for n, m in models.items():
        print(f"  {n}: {m}")

    for round_idx in range(cfg.rounds):
        order = names[:]
        rng.shuffle(order)
        for name in order:
            p = participants[name]
            try:
                result = run_turn(client, p, mp, max_tokens=cfg.max_tokens_per_turn)
            except Exception as e:
                result = {"actor": name, "model": p.model, "action": "error", "error": str(e)}
                time.sleep(1)
            # Update budgets from any deals we settled this turn.
            for deal in mp.deals:
                # Buyers pay, sellers receive — applied once via deal_id tracking.
                pass
            result["round"] = round_idx
            with turn_log_path.open("a") as f:
                f.write(json.dumps(result) + "\n")
            print(f"  r{round_idx:02d} {name:>12} ({p.model.split('-')[1]:>5}): {result.get('action')}")

        # Re-derive budgets from settled deals so any deals from this round count.
        for name, p in participants.items():
            spent = sum(d.price for d in mp.deals if d.buyer == name)
            earned = sum(d.price for d in mp.deals if d.seller == name)
            p.budget_remaining = initial_budget - spent  # buyer-side cap (mirrors experiment)
            _ = earned

    summary = {
        "run": cfg.name, "mode": mode,
        "n_participants": len(names),
        "n_listings": len(mp.listings),
        "n_deals": len(mp.deals),
        "total_value": round(sum(d.price for d in mp.deals), 2),
        "models": models,
        "deals": [asdict(d) for d in mp.deals],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nRun {cfg.name} complete: {summary['n_deals']} deals, ${summary['total_value']:.2f} total value.")
    return summary
