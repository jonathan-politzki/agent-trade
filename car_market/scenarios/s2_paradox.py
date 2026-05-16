"""S2 backup: deterministic-only regret-vs-pool-size curve.

Compares two buyer policies (no LLM):
- first_acceptable: visit listings in search order, buy first with U > 0
- full_search: enumerate all listings, pick argmax of U
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from ..archetypes import population_sample, build_listing
from ..generator import generate
from ..personas import load_personas, utility


def _best_full(listings, persona):
    best_u = float("-inf")
    for l in listings:
        u = utility(l.car, l.listing_condition, l.asking_price, persona)
        if u > best_u:
            best_u = u
    return best_u if best_u != float("-inf") else 0.0


def _first_acceptable(listings, persona):
    for l in listings:
        u = utility(l.car, l.listing_condition, l.asking_price, persona)
        if u != float("-inf") and u > 0:
            return u
    return 0.0


def run(seed: int = 0, m_values=(10, 25, 50, 100, 200), n_seeds: int = 10,
         out_dir: str = "runs/s2") -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    personas = load_personas()
    rows = []
    for m in m_values:
        for sd in range(n_seeds):
            cars = generate(seed=seed * 1000 + sd, n=m)
            archetypes = population_sample(seed=seed * 10000 + sd, k=m)
            listings = [
                build_listing(c, a, seller_id=f"S_{i}",
                                 rng=random.Random(sd * m + i))
                for i, (c, a) in enumerate(zip(cars, archetypes))
            ]
            for persona in personas:
                full = _best_full(listings, persona)
                first = _first_acceptable(listings, persona)
                rows.append({
                    "m": m, "seed": sd, "persona": persona.persona_id,
                    "full_search_U": full,
                    "first_acceptable_U": first,
                    "regret": full - first,
                })
    (out / "s2_rows.json").write_text(json.dumps(rows, indent=2))
    return {"n_rows": len(rows), "out": str(out / "s2_rows.json")}
