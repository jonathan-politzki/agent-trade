"""Aggregate metrics from a sweep's results.jsonl.

Designed to be the input layer for downstream viz/sims (v2). Two roles:
  - Flat-row export to CSV for notebooks / pandas / dashboards.
  - Quick on-the-CLI summary tables: close rate, mean premium by persona pair,
    susceptibility by tactic × buyer.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


def load_results(sweep_dir: Path) -> list[dict]:
    rows = []
    for line in (sweep_dir / "results.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if "error" in d:
            continue
        rows.append(d)
    return rows


def to_csv(sweep_dir: Path) -> Path:
    rows = load_results(sweep_dir)
    if not rows:
        return sweep_dir / "results.csv"
    flat = []
    for r in rows:
        flat_r = {k: v for k, v in r.items() if not isinstance(v, (list, dict))}
        flat_r["inspections_used"] = ",".join(r.get("inspections_used", []))
        flat_r["revealed_facts_n"] = len(r.get("revealed_facts", []))
        flat.append(flat_r)
    out = sweep_dir / "results.csv"
    fieldnames = sorted({k for r in flat for k in r.keys()})
    with out.open("w") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in flat:
            w.writerow(r)
    return out


def _mean(xs: list[float]) -> float | None:
    return statistics.mean(xs) if xs else None


def summary(rows: list[dict]) -> dict:
    n = len(rows)
    deals = [r for r in rows if r["outcome"] == "deal"]
    walks = [r for r in rows if r["outcome"].startswith("walk_away")]
    timeouts = [r for r in rows if r["outcome"] == "timeout"]

    by_seller: dict[str, list[float]] = defaultdict(list)
    by_buyer: dict[str, list[float]] = defaultdict(list)
    by_pair: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_tactic_x_buyer: dict[tuple[str, str], list[float]] = defaultdict(list)
    close_by_pair: dict[tuple[str, str], list[int]] = defaultdict(list)

    for r in rows:
        sp, bp = r["seller_persona_id"], r["buyer_persona_id"]
        close_by_pair[(sp, bp)].append(1 if r["outcome"] == "deal" else 0)
        if r["outcome"] != "deal" or r.get("premium_over_true") is None:
            continue
        prem = r["premium_over_true"]
        by_seller[sp].append(prem)
        by_buyer[bp].append(prem)
        by_pair[(sp, bp)].append(prem)
        if r.get("hacking_tactic"):
            by_tactic_x_buyer[(r["hacking_tactic"], bp)].append(prem)

    return {
        "n_sessions": n,
        "n_deals": len(deals),
        "n_walks": len(walks),
        "n_timeouts": len(timeouts),
        "close_rate": (len(deals) / n) if n else 0.0,
        "mean_premium_over_true_when_deal": _mean([r["premium_over_true"] for r in deals if r.get("premium_over_true") is not None]),
        "mean_premium_over_listed_when_deal": _mean([r["premium_over_listed"] for r in deals if r.get("premium_over_listed") is not None]),
        "premium_by_seller_persona": {k: _mean(v) for k, v in by_seller.items()},
        "premium_by_buyer_persona": {k: _mean(v) for k, v in by_buyer.items()},
        "premium_by_seller_x_buyer": {f"{a}__x__{b}": _mean(v) for (a, b), v in by_pair.items()},
        "close_rate_by_seller_x_buyer": {f"{a}__x__{b}": _mean(v) for (a, b), v in close_by_pair.items()},
        "premium_by_tactic_x_buyer": {f"{t}__x__{b}": _mean(v) for (t, b), v in by_tactic_x_buyer.items()},
    }


def pretty(summary_dict: dict) -> str:
    lines = []
    s = summary_dict
    lines.append(f"sessions: {s['n_sessions']}  deals: {s['n_deals']}  walks: {s['n_walks']}  timeouts: {s['n_timeouts']}  close rate: {s['close_rate']:.1%}")
    if s.get("mean_premium_over_true_when_deal") is not None:
        lines.append(f"mean premium vs true_value (deals only): {s['mean_premium_over_true_when_deal']:+.1%}")
        lines.append(f"mean premium vs listed_price (deals only): {s['mean_premium_over_listed_when_deal']:+.1%}")
    lines.append("")
    lines.append("by SELLER persona (mean premium vs true):")
    for k, v in sorted((s.get("premium_by_seller_persona") or {}).items()):
        lines.append(f"  {k:>12}: {v:+.1%}" if v is not None else f"  {k:>12}: —")
    lines.append("")
    lines.append("by BUYER persona (mean premium vs true paid):")
    for k, v in sorted((s.get("premium_by_buyer_persona") or {}).items()):
        lines.append(f"  {k:>12}: {v:+.1%}" if v is not None else f"  {k:>12}: —")
    lines.append("")
    lines.append("seller × buyer (mean premium vs true | close rate):")
    pairs = (s.get("premium_by_seller_x_buyer") or {})
    closes = (s.get("close_rate_by_seller_x_buyer") or {})
    for k in sorted(closes):
        prem = pairs.get(k)
        prem_str = f"{prem:+.1%}" if prem is not None else "    —"
        lines.append(f"  {k:>32}: {prem_str}  | close {closes[k]:.1%}")
    if s.get("premium_by_tactic_x_buyer"):
        lines.append("")
        lines.append("tactic × buyer (susceptibility — mean premium vs true):")
        for k, v in sorted(s["premium_by_tactic_x_buyer"].items()):
            lines.append(f"  {k:>40}: {v:+.1%}" if v is not None else f"  {k:>40}: —")
    return "\n".join(lines)
