"""S3 open-market scenario — headline.

In `fast` mode:
- k sellers initialised with archetype draws and seeded inventories.
- m buyers arrive by Poisson process over T steps; each draws a persona.
- At arrival, buyer searches top-K, picks the listing she prefers, opens
  an offer at her policy bid, the seller responds (accept/counter/decline).
- A single counter triggers one more buyer round (so max 2 effective price
  rounds per negotiation), counted against max_neg_turns.
- Outcomes go to JSONL via the marketplace log AND per_deal.json.

Per-deal records include oracle columns: buyer_surplus, seller_surplus,
deal_welfare, true_value, listing_condition, true_condition, archetype.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from ..archetypes import build_listing, population_sample
from ..config import S3Config
from ..evaluator import deal_welfare, run_metrics
from ..generator import generate
from ..marketplace import CarMarketplace
from ..personas import load_personas, utility, welfare_value
from ..policies import HeuristicBuyer, HeuristicSeller
from ..scheduler import poisson_arrivals


def run(cfg: S3Config) -> dict:
    rng = random.Random(cfg.seed)
    out_dir = Path(cfg.out_dir) / f"s3_seed{cfg.seed}_gamma{cfg.reputation_gamma}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "events.jsonl"

    mp = CarMarketplace(
        run_name=f"s3_seed{cfg.seed}_gamma{cfg.reputation_gamma}",
        reputation_gamma=cfg.reputation_gamma,
        log_path=log_path,
    )

    # ---- seed sellers + inventories ----
    archetypes = population_sample(seed=cfg.seed, k=cfg.k_sellers)
    sellers: dict[str, HeuristicSeller] = {}
    cars_by_listing: dict[str, "CarSpec"] = {}
    car_idx = 0
    for i, archetype in enumerate(archetypes):
        seller_id = f"S_{i+1:02d}"
        n_inv = rng.randint(*cfg.inventory_per_seller)
        cars = generate(seed=cfg.seed * 1000 + i, n=n_inv)
        for c in cars:
            l = build_listing(
                c, archetype, seller_id=seller_id,
                rng=random.Random(cfg.seed * 10000 + car_idx),
                listing_id=f"L_{car_idx+1:05d}",
            )
            mp.add_listing(l)
            cars_by_listing[l.listing_id] = c
            car_idx += 1
        sellers[seller_id] = HeuristicSeller(
            seller_id=seller_id, archetype=archetype,
            rng=random.Random(cfg.seed * 100 + i),
        )

    # ---- buyer arrivals ----
    arrivals = poisson_arrivals(m=cfg.m_buyers, T=cfg.T, seed=cfg.seed + 1)
    personas = load_personas()
    per_deal: list[dict] = []
    buyers_processed = 0
    no_deal_count = 0

    for t_idx, t in enumerate(arrivals):
        persona = personas[(cfg.seed + t_idx) % len(personas)]
        buyer_id = f"B_{t_idx+1:04d}"
        buyer = HeuristicBuyer(
            buyer_id=buyer_id, persona=persona,
            rng=random.Random(cfg.seed * 1000 + t_idx),
        )
        buyers_processed += 1
        q = persona.allowed_bodies[0]
        cards = mp.search(query=q, max_results=10)
        ranked = buyer.rank_listings(cards, cars_by_listing)
        deal_made = False
        for lid in ranked[:cfg.max_neg_turns]:
            card = next(c for c in cards if c.listing_id == lid)
            car = cars_by_listing[lid]
            bid = buyer.propose_price(card, car)
            off = mp.make_offer(buyer=buyer_id, listing_id=lid, price=bid, message="(fast)")
            if off is None:
                continue
            seller = sellers[card.seller_id]
            step = seller.respond_to_offer(
                car=car, asking_price=card.asking_price, offer_price=bid,
            )
            if step.action == "accept":
                d = mp.respond_to_offer(
                    seller=seller.seller_id, offer_id=off.offer_id,
                    action="accept", counter_price=None, message="(fast)",
                )
                if d is not None:
                    # Ex-post welfare: based on TRUE condition (what buyer
                    # actually got), not listing_condition (what she perceived).
                    # buyer_utility here is GROSS max WTP — evaluator subtracts price.
                    bu = welfare_value(car, car.true_condition, persona)
                    bs, ss, dw = deal_welfare(price=d.price, true_value=car.true_value,
                                                 buyer_utility=bu)
                    per_deal.append({
                        "deal_id": d.deal_id, "buyer": buyer_id, "seller": seller.seller_id,
                        "listing_id": lid, "price": d.price,
                        "true_value": car.true_value,
                        "buyer_utility": bu,
                        "buyer_surplus": bs, "seller_surplus": ss, "deal_welfare": dw,
                        "listing_condition": card.listing_condition,
                        "true_condition": car.true_condition,
                        "seller_archetype": seller.archetype.name,
                        "persona": persona.persona_id,
                    })
                    deal_made = True
                    break
            elif step.action == "counter":
                mp.respond_to_offer(
                    seller=seller.seller_id, offer_id=off.offer_id,
                    action="counter", counter_price=step.counter_price, message="(fast)",
                )
                # Buyer evaluates counter as a new asking price. If her WTP >= counter,
                # she accepts by re-offering at the counter price.
                wtp_under_listing = buyer.propose_price(card, car) / 0.90
                if step.counter_price <= wtp_under_listing:
                    new_off = mp.make_offer(
                        buyer=buyer_id, listing_id=lid,
                        price=step.counter_price, message="(accepts counter)",
                    )
                    if new_off is not None:
                        d = mp.respond_to_offer(
                            seller=seller.seller_id, offer_id=new_off.offer_id,
                            action="accept", counter_price=None, message="(close)",
                        )
                        if d is not None:
                            bu = welfare_value(car, car.true_condition, persona)
                            bs, ss, dw = deal_welfare(price=d.price, true_value=car.true_value,
                                                         buyer_utility=bu)
                            per_deal.append({
                                "deal_id": d.deal_id, "buyer": buyer_id, "seller": seller.seller_id,
                                "listing_id": lid, "price": d.price,
                                "true_value": car.true_value, "buyer_utility": bu,
                                "buyer_surplus": bs, "seller_surplus": ss, "deal_welfare": dw,
                                "listing_condition": card.listing_condition,
                                "true_condition": car.true_condition,
                                "seller_archetype": seller.archetype.name,
                                "persona": persona.persona_id,
                            })
                            deal_made = True
                            break
            else:
                continue
        if not deal_made:
            no_deal_count += 1
            mp.buyer_withdraw(buyer_id)

    summary = {
        "run": mp.run_name, "seed": cfg.seed,
        "reputation_gamma": cfg.reputation_gamma,
        "k_sellers": cfg.k_sellers, "m_buyers_expected": cfg.m_buyers,
        "m_buyers_actual": buyers_processed,
        "deals": len(per_deal), "no_deal_buyers": no_deal_count,
        "listings_total": len(mp.listings),
        "listings_sold": sum(1 for l in mp.listings.values() if l.sold),
    }
    summary.update(run_metrics(per_deal, no_deal_count))
    (out_dir / "per_deal.json").write_text(json.dumps(per_deal, indent=2))
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary
