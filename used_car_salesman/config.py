"""Shared config for the used-car-salesman experiment."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

OPUS = "claude-opus-4-5"
HAIKU = "claude-haiku-4-5"

# Models the experiment cycles through. Add Gemini / GPT here once the
# corresponding clients are wired up (orchestrator currently uses Anthropic).
DEFAULT_SELLER_MODEL = OPUS
DEFAULT_BUYER_MODEL = OPUS

# Where to put generated artifacts. Override per-CLI if needed.
REPO_ROOT = Path(__file__).resolve().parent.parent
CARS_DIR = REPO_ROOT / "cars"
PERSONAS_DIR = REPO_ROOT / "personas"
TACTICS_PATH = REPO_ROOT / "tactics" / "catalog.json"
SWEEPS_DIR = REPO_ROOT / "sweeps"

# Session limits.
DEFAULT_MAX_TURNS = 25
INSPECTION_COST = 150.0


@dataclass(frozen=True)
class SessionConfig:
    """One buyer-seller-car dialog session."""
    car_id: str
    seller_persona_id: str
    buyer_persona_id: str
    seller_model: str = DEFAULT_SELLER_MODEL
    buyer_model: str = DEFAULT_BUYER_MODEL
    buyer_options_narrowed: bool = True
    seller_knows_buyer: bool = False
    hacking_tactic: str | None = None
    max_turns: int = DEFAULT_MAX_TURNS
    inspection_cost: float = INSPECTION_COST
    seed: int = 0


def api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set; copy .env.example to .env.")
    return key
