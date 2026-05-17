"""Pack a completed sweep into ui/data/ for visualization.

Usage:
  python3 ui/import_sweep.py sweeps/e1_buyer_model_susceptibility

What it does:
  - reads results.jsonl              → ui/data/sessions.json
  - reads cars/generated/fleet.json  → ui/data/cars.json
  - copies the analysis agent's annotations file if present;
    otherwise writes a minimal {} (the UI derives inspection reveals on the fly)
  - selects a handful of "headline" sessions and copies their transcripts in.

The selection rule for replayable transcripts:
  - top 1 by premium (the worst extraction)
  - top 1 by negative premium (best buyer outcome)
  - 1 walk_away
  - 1 timeout
  - 1 representative deal near the median premium
This keeps the replay session-picker focused on instructive cases without
flooding it with hundreds of conversations.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parent.parent
UI_DATA = Path(__file__).resolve().parent / "data"


def main(sweep_dir: Path) -> None:
    if not sweep_dir.exists():
        sys.exit(f"sweep dir {sweep_dir} not found")

    results_path = sweep_dir / "results.jsonl"
    if not results_path.exists():
        sys.exit(f"missing {results_path}")

    sessions = [json.loads(line) for line in results_path.read_text().splitlines() if line.strip()]
    print(f"loaded {len(sessions)} sessions from {results_path}")

    # Some sweeps (multi-model) produce colliding session_ids because the upstream
    # generator doesn't fold the model into the ID. Disambiguate now so the UI
    # can key off session_id uniquely. Preserve the on-disk session_id under
    # _disk_session_id so transcript copy still finds the source files.
    seen_ids: dict[str, int] = {}
    for s in sessions:
        sid = s["session_id"]
        s["_disk_session_id"] = sid
        if sid in seen_ids:
            seen_ids[sid] += 1
            suffix = _short_model(s.get("buyer_model"))
            new_sid = f"{sid}__{suffix}"
            counter = 2
            while new_sid in seen_ids:
                new_sid = f"{sid}__{suffix}_{counter}"
                counter += 1
            seen_ids[new_sid] = 1
            s["session_id"] = new_sid
        else:
            seen_ids[sid] = 1

    # Rewrite transcript_path so it resolves relative to ui/data/.
    # Source transcripts live at sweep_dir/<session_id>/transcript.jsonl.
    # We'll copy a curated subset into ui/data/transcripts/<session_id>.jsonl.
    selected_sids = _select_headline_sessions(sessions)
    print(f"selected {len(selected_sids)} headline sessions for replay:")
    for sid in selected_sids:
        print(f"  - {sid}")

    UI_DATA.mkdir(parents=True, exist_ok=True)
    (UI_DATA / "transcripts").mkdir(parents=True, exist_ok=True)

    # Update transcript_path to a canonical location and copy in the files we keep.
    for s in sessions:
        sid = s["session_id"]
        s["transcript_path"] = f"transcripts/{sid}.jsonl"

    sid_to_disk = {s["session_id"]: s["_disk_session_id"] for s in sessions}
    for sid in selected_sids:
        disk_sid = sid_to_disk.get(sid, sid)
        src = sweep_dir / disk_sid / "transcript.jsonl"
        dst = UI_DATA / "transcripts" / f"{sid}.jsonl"
        if src.exists():
            dst.write_text(src.read_text())
        else:
            print(f"  WARNING: no transcript at {src}")

    # Drop the internal _disk_session_id field before serializing.
    for s in sessions:
        s.pop("_disk_session_id", None)

    # Sessions list — full set so the heatmap/aggregate views see everything.
    (UI_DATA / "sessions.json").write_text(json.dumps(sessions, indent=2))

    # Cars: real fleet, since real sessions reference real car_ids.
    fleet_path = ROOT / "cars" / "generated" / "fleet.json"
    if fleet_path.exists():
        fleet = json.loads(fleet_path.read_text())
        (UI_DATA / "cars.json").write_text(json.dumps(fleet, indent=2))
        print(f"copied fleet ({len(fleet)} cars)")
    else:
        print("WARNING: cars/generated/fleet.json not found — UI will use whatever cars.json exists")

    # Personas and tactics are stable; refresh from repo.
    tactics = json.loads((ROOT / "tactics" / "catalog.json").read_text())
    (UI_DATA / "tactics.json").write_text(json.dumps(tactics, indent=2))

    sellers = {p.stem: json.loads(p.read_text())
               for p in (ROOT / "personas" / "sellers").glob("*.json")}
    buyers = {p.stem: json.loads(p.read_text())
              for p in (ROOT / "personas" / "buyers").glob("*.json")}
    (UI_DATA / "personas.json").write_text(json.dumps({"sellers": sellers, "buyers": buyers}, indent=2))

    # Annotations: only honor an annotations.json the analysis agent dropped here;
    # otherwise empty (replay.js auto-derives inspection reveals).
    ann_src = sweep_dir / "annotations.json"
    if ann_src.exists():
        (UI_DATA / "session_annotations.json").write_text(ann_src.read_text())
        print(f"copied annotations.json")
    else:
        # Preserve any existing annotations file (e.g. the demo ones), but clear
        # references to sessions that aren't in this sweep so the replay picker
        # doesn't list orphans.
        existing = UI_DATA / "session_annotations.json"
        if existing.exists():
            try:
                existing_ann = json.loads(existing.read_text())
            except Exception:
                existing_ann = {}
            sweep_sids = {s["session_id"] for s in sessions}
            pruned = {k: v for k, v in existing_ann.items() if k in sweep_sids}
            existing.write_text(json.dumps(pruned, indent=2))
        else:
            (UI_DATA / "session_annotations.json").write_text("{}")

    # For replayable sessions, the UI looks at intersection of annotations + sessions.
    # We want all selected_sids to be replayable, so write minimal {} entries for them
    # if they're not in annotations yet — they'll auto-derive in replay.js.
    ann_path = UI_DATA / "session_annotations.json"
    ann = json.loads(ann_path.read_text())
    for sid in selected_sids:
        ann.setdefault(sid, {})
    ann_path.write_text(json.dumps(ann, indent=2))

    print(f"\nwrote ui/data/. open ui/index.html (via `python3 -m http.server 8765` from ui/).")


def _short_model(m: str | None) -> str:
    if not m: return "unknown"
    if "opus" in m and "4-7" in m:           return "opus47"
    if "opus" in m and "4-5" in m:           return "opus45"
    if "opus" in m:                           return "opus"
    if "haiku" in m and "4-5" in m:          return "haiku45"
    if "haiku" in m:                          return "haiku"
    if "sonnet" in m:                         return "sonnet"
    if "gemini" in m and "flash-lite" in m:  return "geminiflite"
    if "gemini" in m and "flash" in m:        return "geminif"
    if "gemini" in m and "pro" in m:          return "geminipro"
    if "gemini" in m:                         return "gemini"
    if "gpt-4o-mini" in m:                    return "gpt4omini"
    if "gpt-4o" in m:                         return "gpt4o"
    if "gpt" in m:                            return "gpt"
    return m.replace("/", "_").replace("-", "")[:12]


def _select_headline_sessions(sessions: list[dict]) -> list[str]:
    """Pick a small instructive subset to make replayable."""
    deals = [s for s in sessions if s["outcome"] == "deal"]
    walks = [s for s in sessions if s["outcome"] == "walk_away_buyer"]
    timeouts = [s for s in sessions if s["outcome"] == "timeout"]

    selected: list[str] = []

    if deals:
        deals_sorted = sorted(deals, key=lambda s: (s["premium_over_true"] or 0))
        # Highest premium — the worst extraction.
        selected.append(deals_sorted[-1]["session_id"])
        # Lowest (most-negative) premium — best buyer outcome.
        selected.append(deals_sorted[0]["session_id"])
        # Closest to median.
        if len(deals_sorted) >= 3:
            mid = len(deals_sorted) // 2
            selected.append(deals_sorted[mid]["session_id"])

    if walks:
        # Walk on the worst (lowest true_value vs asking) car if possible.
        walks_sorted = sorted(walks, key=lambda s: (s["true_value"] / max(s["asking_price"], 1)))
        selected.append(walks_sorted[0]["session_id"])

    if timeouts:
        # A timeout where the buyer used the most inspections is the most
        # instructive — the buyer was working hard.
        timeouts_sorted = sorted(timeouts, key=lambda s: -(s["n_inspections"] or 0))
        selected.append(timeouts_sorted[0]["session_id"])

    # De-duplicate while preserving order.
    out, seen = [], set()
    for sid in selected:
        if sid not in seen:
            out.append(sid)
            seen.add(sid)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 ui/import_sweep.py <sweep_dir>")
    main(Path(sys.argv[1]).resolve())
