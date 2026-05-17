"""Concat every sweeps/*/results.jsonl into ui/data/sessions.json.

When two sweeps produce the same session_id (same car/personas/models/seed
but a different run), disambiguate by suffixing _<sweep_id> rather than
losing the duplicate. Tags each row with sweep_id so a UI filter can split
on it. Copies all transcripts.
"""
import json, shutil
from pathlib import Path
from collections import Counter

ROOT = Path("/Users/robertmueller/Desktop/agents/agent-trade")
SWEEPS = ROOT / "sweeps"
UI_DATA = ROOT / "ui" / "data"
UI_TRANSCRIPTS = UI_DATA / "transcripts"

rows_per_sweep = []
for sweep_dir in sorted(SWEEPS.iterdir()):
    results = sweep_dir / "results.jsonl"
    if not results.exists():
        continue
    sweep_id = sweep_dir.name
    bucket = []
    for line in results.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not r.get("session_id"):
            continue
        r["sweep_id"] = sweep_id
        bucket.append(r)
    rows_per_sweep.append((sweep_id, bucket))
    print(f"  {len(bucket):>4} rows from {sweep_id}")

# Build a single list, disambiguating colliding session_ids by appending _<sweep_id>.
seen = {}
final = []
for sweep_id, bucket in rows_per_sweep:
    for r in bucket:
        sid = r["session_id"]
        if sid in seen:
            r["_orig_session_id"] = sid
            r["session_id"] = f"{sid}__{sweep_id}"
        seen[r["session_id"]] = True
        final.append(r)

print(f"\nTotal rows after disambiguation: {len(final)}")
print("sweep_id distribution:", dict(Counter(r["sweep_id"] for r in final)))

(UI_DATA / "sessions.json").write_text(json.dumps(final, indent=2))
print(f"Wrote ui/data/sessions.json")

# Copy transcripts; account for renamed session_ids
UI_TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
copied = 0
for r in final:
    sid_disk = r.get("_orig_session_id", r["session_id"])
    sweep = r["sweep_id"]
    src = SWEEPS / sweep / sid_disk / "transcript.jsonl"
    if src.exists():
        dst = UI_TRANSCRIPTS / f"{r['session_id']}.jsonl"
        if not dst.exists() or src.stat().st_size != dst.stat().st_size:
            shutil.copy2(src, dst)
            copied += 1
print(f"Copied {copied} transcripts")
