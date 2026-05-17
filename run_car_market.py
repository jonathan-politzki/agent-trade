"""CLI entrypoint for the used-car marketplace.

Examples:
  python run_car_market.py headline                       # 30-seed fast sweep, render chart
  python run_car_market.py headline --seeds 10            # smaller sweep
  python run_car_market.py record --seed 0                # record one llm-mode pair to cache
  python run_car_market.py demo --seed 0                  # live replay (zero API)
  python run_car_market.py one --seed 0 --gamma 0.5 --mode fast
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from car_market.aggregate import sweep, welfare_delta_report
from car_market.config import S3Config
from car_market.plots import welfare_delta_bar
from car_market.scenarios.s3_open_market import run as run_s3


def cmd_headline(args):
    rows = sweep(seeds=list(range(args.seeds)), gammas=[0.0, 0.5])
    report = welfare_delta_report(rows["rows"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    welfare_delta_bar(report, out)
    print(json.dumps(report, indent=2))
    print(f"chart: {out}")


def cmd_record(args):
    for gamma in (0.0, 0.5):
        s = run_s3(S3Config(seed=args.seed, reputation_gamma=gamma, mode="llm"))
        print(json.dumps({"gamma": gamma, **s}, indent=2))


def cmd_demo(args):
    visible = run_s3(S3Config(seed=args.seed, reputation_gamma=0.5, mode="replay"))
    hidden = run_s3(S3Config(seed=args.seed, reputation_gamma=0.0, mode="replay"))
    print("VISIBLE:", json.dumps(visible, indent=2))
    print("HIDDEN: ", json.dumps(hidden, indent=2))
    print("delta_welfare =",
           round(visible.get("total_welfare", 0) - hidden.get("total_welfare", 0)))


def cmd_one(args):
    s = run_s3(S3Config(seed=args.seed, reputation_gamma=args.gamma, mode=args.mode))
    print(json.dumps(s, indent=2))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("headline")
    p1.add_argument("--seeds", type=int, default=30)
    p1.add_argument("--out", type=str, default="runs/headline_welfare_delta.png")
    p1.set_defaults(func=cmd_headline)

    p2 = sub.add_parser("record")
    p2.add_argument("--seed", type=int, default=0)
    p2.set_defaults(func=cmd_record)

    p3 = sub.add_parser("demo")
    p3.add_argument("--seed", type=int, default=0)
    p3.set_defaults(func=cmd_demo)

    p4 = sub.add_parser("one")
    p4.add_argument("--seed", type=int, default=0)
    p4.add_argument("--gamma", type=float, default=0.5)
    p4.add_argument("--mode", type=str, default="fast",
                     choices=["fast", "llm", "replay"])
    p4.set_defaults(func=cmd_one)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
