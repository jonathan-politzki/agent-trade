"""Persona loader. Personas are flat JSON; this just provides a typed accessor
and a way to inject buyer-context into a seller's prompt for the
`seller_knows_buyer` toggle.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import PERSONAS_DIR, TACTICS_PATH


@dataclass
class Persona:
    persona_id: str
    side: str               # "seller" | "buyer"
    display_name: str
    system_prompt: str
    raw: dict               # full JSON for additional fields

    @property
    def knowledge_level(self) -> float: return float(self.raw.get("knowledge_level", 0.5))
    @property
    def patience(self) -> float: return float(self.raw.get("patience", 0.5))
    @property
    def deceptiveness(self) -> float: return float(self.raw.get("deceptiveness", 0.0))
    @property
    def pressure(self) -> float: return float(self.raw.get("pressure", 0.0))
    @property
    def skepticism(self) -> float: return float(self.raw.get("skepticism", 0.5))
    @property
    def inspection_propensity(self) -> float: return float(self.raw.get("inspection_propensity", 0.5))
    @property
    def default_budget(self) -> float: return float(self.raw.get("default_budget", 20000))

    @property
    def karma_score(self) -> float | None:
        """Reputation prior in [-1, +1]. None if not set in the JSON."""
        v = self.raw.get("karma_score")
        return None if v is None else float(v)

    @property
    def archetype(self) -> str | None:
        v = self.raw.get("archetype")
        return None if v is None else str(v)

    @property
    def signature_line(self) -> str:
        return str(self.raw.get("signature_line", ""))

    @property
    def location(self) -> str:
        return str(self.raw.get("location", ""))


def load_persona(path: Path) -> Persona:
    data = json.loads(Path(path).read_text())
    return Persona(
        persona_id=data["persona_id"],
        side=data["side"],
        display_name=data.get("display_name", data["persona_id"]),
        system_prompt=data["system_prompt"],
        raw=data,
    )


def load_persona_by_id(persona_id: str, side: str) -> Persona:
    path = PERSONAS_DIR / f"{side}s" / f"{persona_id}.json"
    return load_persona(path)


def list_personas(side: str) -> list[Persona]:
    folder = PERSONAS_DIR / f"{side}s"
    return [load_persona(p) for p in sorted(folder.glob("*.json"))]


def load_tactic(tactic_id: str) -> dict:
    catalog = json.loads(TACTICS_PATH.read_text())
    if tactic_id not in catalog:
        raise KeyError(f"Tactic '{tactic_id}' not in {TACTICS_PATH}. Available: {list(catalog)}")
    return catalog[tactic_id]


def list_tactics() -> dict:
    return json.loads(TACTICS_PATH.read_text())


def buyer_profile_brief(buyer: Persona) -> str:
    """Short briefing the seller sees when `seller_knows_buyer` is on."""
    return (
        f"BUYER PROFILE (provided to you in advance):\n"
        f"  display name: {buyer.display_name}\n"
        f"  knowledge level: {buyer.knowledge_level:.2f} (0=novice, 1=expert)\n"
        f"  skepticism: {buyer.skepticism:.2f}\n"
        f"  inspection propensity: {buyer.inspection_propensity:.2f}\n"
        f"  patience: {buyer.patience:.2f}\n"
        f"  approximate budget: ${buyer.default_budget:,.0f}\n"
        f"  one-line summary: {buyer.system_prompt.split('.')[0]}."
    )
