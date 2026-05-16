"""Synthetic car dataset generator.

For each archetype + severity profile, ask Claude to reason about:
  - a realistic public listing (trim details, condition descriptor, asking price, dealer pitch),
  - a set of private facts at the requested severity (or none if clean),
  - the public-fair-value (what KBB-ish would say for the public side),
  - the true_value (what the car is actually worth given the private facts).

This is the contract layer. When a teammate's real dataset shows up,
write an adapter that emits Car objects in the same shape and the rest
of the pipeline keeps running. The Car schema in `car.py` is the API.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from anthropic import Anthropic

from .car import Car, PrivateFact
from .config import OPUS


GEN_SYSTEM = """You are a senior used-car appraiser. You produce realistic
synthetic car listings for a research dataset that studies information
asymmetry in agent-mediated negotiations. You reason carefully about
price impact: be specific about why each private fact moves true_value,
and ensure public_fair_value reflects what a buyer relying only on the ad
would reasonably pay. Output ONLY valid JSON matching the schema given."""


SEVERITY_GUIDE = {
    "clean":    "no significant private issues — at most one cosmetic note. true_value ≈ public_fair_value.",
    "minor":    "1-2 minor private facts (small cosmetic damage, lapsed maintenance interval, single carfax flag). Combined hit ~3-8% of public_fair_value.",
    "moderate": "2-3 private facts including one notable mechanical or history issue (accident history, oil consumption, transmission early-warning, prior fleet use). Combined hit ~10-20%.",
    "severe":   "3-5 private facts including at least one major issue (rolled-back odometer, salvage/rebuilt title, engine/transmission failure imminent, structural damage). Combined hit ~25-45%.",
}


SCHEMA_PROMPT = """Generate the dataset entry for the following car.

Archetype:
  car_id: {car_id}
  year: {year}
  make: {make}
  model: {model}
  trim: {trim}
  approximate mileage: {approx_mileage}
  severity profile: {severity}  ({severity_desc})

Rules:
  - Pick an asking_price that is realistic for this car's public view (year, mileage, trim, condition) in today's market.
  - Generate a dealer_pitch (2-3 sentences) — the kind of marketing copy a used-car listing actually carries. It may emphasize positives.
  - Generate private_facts according to the severity profile. Each fact has:
      focus_area: one of [engine, transmission, body, history, title, interior]
      summary: short, specific, plausible (e.g. "transmission downshifts harshly between 2-3 when cold").
      severity: 1-5 (1=cosmetic, 5=major safety/value).
      price_impact_usd: a NEGATIVE number (this fact knocks $X off true_value).
  - If the severity profile involves a rolled-back odometer, set real_mileage higher than odometer_miles and include a "history" fact noting it. Otherwise set real_mileage equal to odometer_miles.
  - public_fair_value: what a knowledgeable buyer relying ONLY on the public ad would pay (close to asking_price but not necessarily equal — the ad may be slightly above market).
  - true_value: public_fair_value plus the sum of all price_impact_usd values (so true_value <= public_fair_value).
  - reasoning: 2-4 sentences explaining your price logic.

Output JSON only, matching this exact shape (no extra fields):

{{
  "car_id": "{car_id}",
  "year": {year},
  "make": "{make}",
  "model": "{model}",
  "trim": "{trim}",
  "odometer_miles": <int>,
  "exterior_condition": "<excellent|good|fair|rough>",
  "asking_price": <number>,
  "dealer_pitch": "<string>",
  "real_mileage": <int>,
  "private_facts": [
    {{"focus_area": "<one of engine|transmission|body|history|title|interior>",
      "summary": "<string>",
      "severity": <1-5>,
      "price_impact_usd": <negative number>}}
  ],
  "public_fair_value": <number>,
  "true_value": <number>,
  "reasoning": "<string>"
}}
"""


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n", "", s)
        s = re.sub(r"\n```\s*$", "", s)
    return s


def generate_car(client: Anthropic, archetype: dict, *, model: str = OPUS, max_tokens: int = 2000) -> Car:
    severity = archetype.get("severity_profile", "minor")
    prompt = SCHEMA_PROMPT.format(
        severity_desc=SEVERITY_GUIDE.get(severity, SEVERITY_GUIDE["minor"]),
        severity=severity,
        **archetype,
    )
    resp = client.messages.create(
        model=model, max_tokens=max_tokens,
        system=GEN_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    data = json.loads(_strip_code_fences(raw))
    return Car.from_json(data)


def generate_fleet(client: Anthropic, archetypes: list[dict], *, model: str = OPUS) -> list[Car]:
    fleet: list[Car] = []
    for arc in archetypes:
        print(f"  generating {arc['car_id']} ({arc.get('severity_profile','?')})...")
        car = generate_car(client, arc, model=model)
        # Sanity: if Claude produced inconsistent values, log it but keep the row.
        impact = sum(f.price_impact_usd for f in car.private_facts)
        expected_true = car.public_fair_value + impact
        if abs(car.true_value - expected_true) > 1.0:
            print(f"    [warn] true_value={car.true_value} but public_fair_value+impacts={expected_true:.0f}")
        fleet.append(car)
    return fleet


def load_archetypes(path: Path) -> list[dict]:
    return json.loads(Path(path).read_text())
