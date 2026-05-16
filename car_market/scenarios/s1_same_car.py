"""S1 backup scenario: fix one car, m sellers across all archetypes,
10 personas. Bilateral 1-on-1 negotiations. Output: 10×m surplus heatmap."""
from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

from ..archetypes import HONEST, MODERATE, AGGRESSIVE, build_listing
from ..generator import CarSpec
from ..marketplace import ListingCard
from ..personas import load_personas, utility
from ..policies import HeuristicBuyer, HeuristicSeller


def run(seed: int = 0, out_dir: str = "runs/s1") -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    # Fixed car: 2018 Honda Accord, 78k miles, true_cond=3.2, true_value=$15400.
    car = CarSpec(
        car_id="C_FIXED", year=2018, make="Honda", model="Accord", body="Sedan",
        mileage=78000, true_condition=3.2, true_value=15400.0,
        seller_floor=13860.0, seller_ceiling=16940.0,
        true_vhr_flags=["NO_SALVAGE_TITLE", "NO_FRAME_DAMAGE",
                         "NO_FLOOD_WATER_DAMAGE", "ACCIDENTS_REPORTED",
                         "NO_ONE_OWNER"],
    )
    personas = load_personas()
    archetypes = [HONEST, MODERATE, AGGRESSIVE]
    # 9 sellers: 3 per archetype.
    surplus = np.zeros((len(personas), 9))
    deal_made_grid = np.zeros((len(personas), 9), dtype=bool)
    for sj in range(9):
        archetype = archetypes[sj // 3]
        sid = f"S1_{sj+1:02d}"
        listing = build_listing(
            car, archetype, seller_id=sid, rng=random.Random(seed * 100 + sj),
        )
        s = HeuristicSeller(
            seller_id=sid, archetype=archetype,
            rng=random.Random(seed * 1000 + sj),
        )
        for pi, persona in enumerate(personas):
            buyer = HeuristicBuyer(
                buyer_id=f"B1_{pi+1:02d}", persona=persona,
                rng=random.Random(seed * 10000 + pi * 100 + sj),
            )
            card = ListingCard(
                listing_id=listing.listing_id, seller_id=sid,
                year=car.year, make=car.make, model=car.model, body=car.body,
                mileage=car.mileage, listing_condition=listing.listing_condition,
                asking_price=listing.asking_price, seller_stars=3.0,
            )
            bid = buyer.propose_price(card, car)
            step = s.respond_to_offer(
                car=car, asking_price=listing.asking_price, offer_price=bid,
            )
            settled_price = None
            if step.action == "accept":
                settled_price = bid
            elif step.action == "counter":
                # Buyer-side check: accept counter if utility >= 0.
                u_at_counter = utility(car, listing.listing_condition,
                                          step.counter_price, persona)
                if u_at_counter > 0:
                    settled_price = step.counter_price
            if settled_price is not None:
                surplus[pi, sj] = settled_price - car.true_value
                deal_made_grid[pi, sj] = True
    out_path = out / "s1_surplus.json"
    out_path.write_text(json.dumps({
        "personas": [p.persona_id for p in personas],
        "sellers": [f"S{i+1}_{['H','M','A'][i//3]}" for i in range(9)],
        "surplus": surplus.tolist(),
        "deals_made": deal_made_grid.tolist(),
    }, indent=2))
    return {
        "out": str(out_path),
        "mean_surplus_when_deal": float(surplus[deal_made_grid].mean()) if deal_made_grid.any() else 0.0,
        "n_deals": int(deal_made_grid.sum()),
        "n_cells": int(surplus.size),
    }
