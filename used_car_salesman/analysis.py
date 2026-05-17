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


def _short_model(m: str) -> str:
    """Compact label. Order matters: check flash-lite BEFORE flash."""
    m = m.lower()
    if m.startswith("claude-opus"): return "opus"
    if m.startswith("claude-sonnet"): return "sonnet"
    if m.startswith("claude-haiku"): return "haiku"
    if m.startswith("gpt-4o-mini"): return "gpt4o-mini"
    if m.startswith("gpt-4o"): return "gpt4o"
    if m.startswith("gpt-4"): return "gpt4"
    if m.startswith("gemini-2.5-flash-lite"): return "gemini-flash-lite"
    if m.startswith("gemini-2.5-flash"): return "gemini-flash"
    if m.startswith("gemini-2.5-pro"): return "gemini-pro"
    return m


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

    # Model-side slicing (the cross-provider headline view).
    by_buyer_model: dict[str, list[float]] = defaultdict(list)
    by_seller_model: dict[str, list[float]] = defaultdict(list)
    close_by_buyer_model: dict[str, list[int]] = defaultdict(list)
    close_by_seller_model: dict[str, list[int]] = defaultdict(list)
    by_buyer_model_x_persona: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_seller_x_buyer_model: dict[tuple[str, str], list[float]] = defaultdict(list)
    close_by_seller_x_buyer_model: dict[tuple[str, str], list[int]] = defaultdict(list)
    by_buyer_model_inspections: dict[str, list[int]] = defaultdict(list)
    by_buyer_model_questions: dict[str, list[int]] = defaultdict(list)
    by_buyer_model_turns: dict[str, list[int]] = defaultdict(list)

    for r in rows:
        sp, bp = r["seller_persona_id"], r["buyer_persona_id"]
        bm, sm = _short_model(r["buyer_model"]), _short_model(r["seller_model"])
        is_deal = (r["outcome"] == "deal")
        close_by_pair[(sp, bp)].append(1 if is_deal else 0)
        close_by_buyer_model[bm].append(1 if is_deal else 0)
        close_by_seller_model[sm].append(1 if is_deal else 0)
        close_by_seller_x_buyer_model[(sm, bm)].append(1 if is_deal else 0)
        # Behavioral metrics — collect regardless of deal/walk.
        by_buyer_model_inspections[bm].append(r.get("n_inspections", 0))
        by_buyer_model_questions[bm].append(r.get("n_questions", 0))
        by_buyer_model_turns[bm].append(r.get("n_turns", 0))
        if not is_deal or r.get("premium_over_true") is None:
            continue
        prem = r["premium_over_true"]
        by_seller[sp].append(prem)
        by_buyer[bp].append(prem)
        by_pair[(sp, bp)].append(prem)
        by_buyer_model[bm].append(prem)
        by_seller_model[sm].append(prem)
        by_buyer_model_x_persona[(bm, bp)].append(prem)
        by_seller_x_buyer_model[(sm, bm)].append(prem)
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
        "premium_by_buyer_model": {k: _mean(v) for k, v in by_buyer_model.items()},
        "premium_by_seller_model": {k: _mean(v) for k, v in by_seller_model.items()},
        "close_rate_by_buyer_model": {k: _mean(v) for k, v in close_by_buyer_model.items()},
        "close_rate_by_seller_model": {k: _mean(v) for k, v in close_by_seller_model.items()},
        "premium_by_buyer_model_x_persona": {f"{m}__x__{p}": _mean(v) for (m, p), v in by_buyer_model_x_persona.items()},
        "premium_by_seller_x_buyer_model": {f"{a}__x__{b}": _mean(v) for (a, b), v in by_seller_x_buyer_model.items()},
        "close_rate_by_seller_x_buyer_model": {f"{a}__x__{b}": _mean(v) for (a, b), v in close_by_seller_x_buyer_model.items()},
        "mean_inspections_by_buyer_model": {k: _mean(v) for k, v in by_buyer_model_inspections.items()},
        "mean_questions_by_buyer_model": {k: _mean(v) for k, v in by_buyer_model_questions.items()},
        "mean_turns_by_buyer_model": {k: _mean(v) for k, v in by_buyer_model_turns.items()},
        "n_deals_by_buyer_model": {k: len(v) for k, v in by_buyer_model.items()},
        "n_deals_by_seller_model": {k: len(v) for k, v in by_seller_model.items()},
        "n_deals_by_seller_x_buyer_model": {f"{a}__x__{b}": len(v) for (a, b), v in by_seller_x_buyer_model.items()},
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

    if s.get("premium_by_buyer_model"):
        lines.append("")
        lines.append("by BUYER model (the headline cross-provider view):")
        lines.append(f"  {'model':>15}  {'n_deals':>8}  {'mean prem':>10}  {'close':>7}  {'inspect':>8}  {'questions':>10}  {'turns':>6}")
        for m in sorted(s["premium_by_buyer_model"]):
            prem = s["premium_by_buyer_model"][m]
            close = (s.get("close_rate_by_buyer_model") or {}).get(m)
            n_deals = (s.get("n_deals_by_buyer_model") or {}).get(m, 0)
            insp = (s.get("mean_inspections_by_buyer_model") or {}).get(m)
            qs = (s.get("mean_questions_by_buyer_model") or {}).get(m)
            turns = (s.get("mean_turns_by_buyer_model") or {}).get(m)
            prem_str = f"{prem:+.1%}" if prem is not None else "    —"
            close_str = f"{close:.0%}" if close is not None else "  —"
            insp_str = f"{insp:.2f}" if insp is not None else "  —"
            qs_str = f"{qs:.1f}" if qs is not None else "  —"
            turns_str = f"{turns:.1f}" if turns is not None else "  —"
            lines.append(f"  {m:>15}  {n_deals:>8}  {prem_str:>10}  {close_str:>7}  {insp_str:>8}  {qs_str:>10}  {turns_str:>6}")

    if s.get("premium_by_buyer_model_x_persona"):
        lines.append("")
        lines.append("buyer model × persona (premium vs true):")
        for k in sorted(s["premium_by_buyer_model_x_persona"]):
            v = s["premium_by_buyer_model_x_persona"][k]
            lines.append(f"  {k:>32}: {v:+.1%}" if v is not None else f"  {k:>32}: —")

    if s.get("premium_by_seller_model"):
        lines.append("")
        lines.append("by SELLER model (the adversary's quality):")
        lines.append(f"  {'model':>20}  {'n_deals':>8}  {'mean prem':>10}  {'close':>7}")
        for m in sorted(s["premium_by_seller_model"]):
            prem = s["premium_by_seller_model"][m]
            close = (s.get("close_rate_by_seller_model") or {}).get(m)
            nd = (s.get("n_deals_by_seller_model") or {}).get(m, 0)
            prem_str = f"{prem:+.1%}" if prem is not None else "    —"
            close_str = f"{close:.0%}" if close is not None else "  —"
            lines.append(f"  {m:>20}  {nd:>8}  {prem_str:>10}  {close_str:>7}")

    if s.get("premium_by_seller_x_buyer_model"):
        lines.append("")
        lines.append("SELLER model × BUYER model — premium vs true (n deals / close rate):")
        # Build a matrix view if both axes are populated.
        from collections import defaultdict as _dd
        rows_by_sm: dict[str, dict[str, dict]] = _dd(dict)
        for k, v in s["premium_by_seller_x_buyer_model"].items():
            sm, bm = k.split("__x__")
            rows_by_sm[sm][bm] = {"prem": v}
        for k, v in (s.get("close_rate_by_seller_x_buyer_model") or {}).items():
            sm, bm = k.split("__x__")
            rows_by_sm[sm].setdefault(bm, {})["close"] = v
        for k, v in (s.get("n_deals_by_seller_x_buyer_model") or {}).items():
            sm, bm = k.split("__x__")
            rows_by_sm[sm].setdefault(bm, {})["n"] = v
        buyer_axis = sorted({bm for d in rows_by_sm.values() for bm in d})
        lines.append("  " + " " * 22 + "  ".join(f"{bm:>18}" for bm in buyer_axis))
        for sm in sorted(rows_by_sm):
            cells = []
            for bm in buyer_axis:
                c = rows_by_sm[sm].get(bm, {})
                prem = c.get("prem")
                close = c.get("close")
                n = c.get("n", 0)
                if prem is None:
                    cells.append(f"{'—':>18}")
                else:
                    cells.append(f"{prem:+.1%}  n={n}  c={close:.0%}" if close is not None else f"{prem:+.1%}  n={n}")
            lines.append(f"  seller={sm:>14}  " + "  ".join(f"{c:>18}" for c in cells))
    return "\n".join(lines)
