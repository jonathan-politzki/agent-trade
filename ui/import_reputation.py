"""Pack one or more arc/reputation sweeps into ui/data/reputation_arcs.json.

Usage:
  python3 ui/import_reputation.py sweeps/e4_reputation [sweeps/e5_*...]

Multiple sweep dirs are unioned. The view filters by buyer_persona_id so
the same chart machinery works across casual / grandma / mechanic /
engineer arcs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

UI_DATA = Path(__file__).resolve().parent / "data"


def load_sweep(sweep_dir: Path) -> list[dict]:
    trades_path = sweep_dir / "trades.jsonl"
    if not trades_path.exists():
        print(f"  WARN: missing {trades_path}", file=sys.stderr)
        return []
    rows = []
    for line in trades_path.read_text().splitlines():
        if not line.strip(): continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("arc_id") is None or row.get("trade_index") is None:
            continue
        row["_sweep_id"] = sweep_dir.name
        rows.append(row)
    return rows


def main(sweep_dirs: list[Path]) -> None:
    all_trades: list[dict] = []
    sweep_summaries: dict[str, dict] = {}
    for d in sweep_dirs:
        rows = load_sweep(d)
        all_trades.extend(rows)
        summary_path = d / "arc_summary.json"
        if summary_path.exists():
            sweep_summaries[d.name] = json.loads(summary_path.read_text())
        print(f"  {d.name}: {len(rows)} trades")

    if not all_trades:
        sys.exit("no trades loaded")

    # Per-persona summary so the UI can show a one-line description without
    # recomputing every load.
    personas = sorted({t.get("buyer_persona_id", "?") for t in all_trades})
    print(f"\npersonas: {personas}")
    print(f"total trades: {len(all_trades)}")

    payload = {
        "sweep_ids": [d.name for d in sweep_dirs],
        "n_trades": len(all_trades),
        "trades": all_trades,
        "summaries_by_sweep": sweep_summaries,
        "personas": personas,
    }

    UI_DATA.mkdir(parents=True, exist_ok=True)
    out = UI_DATA / "reputation_arcs.json"
    out.write_text(json.dumps(payload, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python3 ui/import_reputation.py <sweep_dir> [<sweep_dir> ...]")
    main([Path(p).resolve() for p in sys.argv[1:]])
