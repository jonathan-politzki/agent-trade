"""Pack an arc/reputation sweep into ui/data/reputation_arcs.json.

Usage:
  python3 ui/import_reputation.py sweeps/e4_reputation

The Reputation view loads this file directly; it's independent of the
main sessions.json (so e1/e3 stay focused on the one-shot question and
e4 stays focused on the longitudinal question).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

UI_DATA = Path(__file__).resolve().parent / "data"


def main(sweep_dir: Path) -> None:
    trades_path = sweep_dir / "trades.jsonl"
    if not trades_path.exists():
        sys.exit(f"missing {trades_path}")

    trades = []
    for line in trades_path.read_text().splitlines():
        if not line.strip(): continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("arc_id") is None or row.get("trade_index") is None:
            continue
        trades.append(row)

    # Optionally pull the per-cell pre-aggregated summary if present.
    summary_path = sweep_dir / "arc_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}

    payload = {
        "sweep_id": sweep_dir.name,
        "n_trades": len(trades),
        "trades": trades,
        "summary": summary,
    }

    UI_DATA.mkdir(parents=True, exist_ok=True)
    out = UI_DATA / "reputation_arcs.json"
    out.write_text(json.dumps(payload, indent=2))
    print(f"wrote {out} ({len(trades)} trades across "
          f"{len({t['arc_id'] for t in trades})} arcs, "
          f"{len({t['trade_index'] for t in trades})} trade indices)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 ui/import_reputation.py <sweep_dir>")
    main(Path(sys.argv[1]).resolve())
