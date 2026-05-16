"""Disk-backed cache for LLM responses. JSONL append-only; reads from a
dict built on init. Keys are (purpose, hashable-context). Used by both
descriptions.py and llm_agent.py."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _key(purpose: str, context: dict) -> str:
    payload = json.dumps({"purpose": purpose, "context": context},
                          sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class LLMCache:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._mem: dict[str, str] = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                self._mem[row["key"]] = row["value"]

    def get(self, purpose: str, context: dict) -> str | None:
        return self._mem.get(_key(purpose, context))

    def put(self, purpose: str, context: dict, value: str) -> None:
        k = _key(purpose, context)
        self._mem[k] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps({"key": k, "purpose": purpose,
                                  "context": context, "value": value},
                                 default=str) + "\n")
