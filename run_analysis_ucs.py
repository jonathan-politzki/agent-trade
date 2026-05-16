"""CLI: print sweep aggregates and emit a flat CSV for downstream viz.

  python3 run_analysis_ucs.py --sweep-id v1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from used_car_salesman.analysis import load_results, summary, pretty, to_csv
from used_car_salesman.config import SWEEPS_DIR


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep-id", required=True)
    ap.add_argument("--root", default=str(SWEEPS_DIR))
    args = ap.parse_args()

    sweep_dir = Path(args.root) / args.sweep_id
    rows = load_results(sweep_dir)
    s = summary(rows)
    print(pretty(s))
    csv_path = to_csv(sweep_dir)
    print(f"\nFlat CSV written to {csv_path}")
    summary_path = sweep_dir / "summary.json"
    summary_path.write_text(json.dumps(s, indent=2, default=str))
    print(f"Summary JSON at {summary_path}")


if __name__ == "__main__":
    main()
