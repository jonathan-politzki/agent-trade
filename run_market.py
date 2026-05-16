"""CLI: launch one or more marketplace runs.

By default, replicates the 2x2 factorial of the original experiment on whatever
participant profiles you point it at:

  python run_market.py --profiles participants/generated --rounds 15
  python run_market.py --profiles participants/generated --rounds 15 --runs A,B
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from project_deal.config import RunConfig
from project_deal.orchestrator import run_market


RUN_MODES = {
    "A": ("all_opus", "Public — all Opus 4.5"),
    "B": ("mixed",    "Public — 50/50 Opus 4.5 / Haiku 4.5"),
    "C": ("mixed",    "Private — 50/50 Opus 4.5 / Haiku 4.5"),
    "D": ("all_opus", "Private — all Opus 4.5"),
}


def main() -> None:
    load_dotenv(override=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", default="participants/generated",
                    help="Directory of {name}.json participant profiles.")
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--runs", default="A,B,C,D", help="Comma-separated runs to execute.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--budget", type=float, default=100.0)
    ap.add_argument("--out", default="runs")
    args = ap.parse_args()

    profile_dir = Path(args.profiles)
    profile_paths = sorted(profile_dir.glob("*.json"))
    if not profile_paths:
        raise SystemExit(f"No profiles in {profile_dir}. Generate some with run_interview.py.")

    for run_name in [r.strip() for r in args.runs.split(",") if r.strip()]:
        mode, _label = RUN_MODES[run_name]
        # Per-run seed so B and C reshuffle model assignment independently
        # (the within-person identification trick from the appendix).
        run_seed = args.seed + sum(ord(c) for c in run_name)
        cfg = RunConfig(name=run_name, rounds=args.rounds, seed=run_seed)
        run_market(profile_paths, cfg, mode=mode,
                   initial_budget=args.budget, out_dir=Path(args.out))


if __name__ == "__main__":
    main()
