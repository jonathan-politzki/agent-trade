"""Named seller personas for the demo. Each maps to a SellerArchetype
(honest/moderate/aggressive) but adds a name, backstory, signature line."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .archetypes import HONEST, MODERATE, AGGRESSIVE, SellerArchetype


SELLER_DIR = Path(__file__).parent / "sellers_data"

_ARCHETYPE_BY_NAME = {"honest": HONEST, "moderate": MODERATE, "aggressive": AGGRESSIVE}


@dataclass(frozen=True)
class SellerPersona:
    seller_id: str
    name: str
    archetype_name: str          # "honest" | "moderate" | "aggressive"
    description: str
    signature_line: str
    location: str

    @property
    def archetype(self) -> SellerArchetype:
        return _ARCHETYPE_BY_NAME[self.archetype_name]


def load_sellers() -> list[SellerPersona]:
    out = []
    for p in sorted(SELLER_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        out.append(SellerPersona(
            seller_id=d["seller_id"], name=d["name"],
            archetype_name=d["archetype"],
            description=d["description"], signature_line=d["signature_line"],
            location=d["location"],
        ))
    return out
