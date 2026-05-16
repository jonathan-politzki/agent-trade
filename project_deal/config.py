"""Shared config for the Project Deal replication."""
from __future__ import annotations

import os
from dataclasses import dataclass

OPUS = "claude-opus-4-5"
HAIKU = "claude-haiku-4-5"

INTERVIEW_MODEL = OPUS
CLASSIFIER_MODEL = HAIKU


@dataclass(frozen=True)
class RunConfig:
    name: str
    rounds: int = 40
    max_tokens_per_turn: int = 1024
    visible_history: int = 30
    seed: int | None = None


def api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Copy .env.example to .env.")
    return key
