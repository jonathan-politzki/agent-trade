"""CLI: analyze completed runs.

  python run_analysis.py                       # analyze everything under runs/
  python run_analysis.py --run runs/B          # one run
"""
from __future__ import annotations

import argparse
from pathlib import Path

from project_deal.analysis import analyze_run, analyze_dir, pretty_print


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="A single run directory (e.g. runs/B).")
    ap.add_argument("--root", default="runs", help="Root of all runs.")
    args = ap.parse_args()

    if args.run:
        pretty_print(analyze_run(Path(args.run)))
    else:
        for report in analyze_dir(Path(args.root)):
            pretty_print(report)


if __name__ == "__main__":
    main()
