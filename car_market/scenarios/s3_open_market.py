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
from ..generator import generate, load_curated_cars
from ..marketplace import CarMarketplace
from ..personas import load_personas, utility, welfare_value
from ..policies import HeuristicBuyer, HeuristicSeller
from ..scheduler import poisson_arrivals


def _dump_snapshots(
    out_dir: Path,
    mp: CarMarketplace,
    cars_by_listing: dict,
    archetype_by_seller: dict,
    seller_name_by_seller: dict | None = None,
    seller_signature_by_seller: dict | None = None,
) -> None:
    """Write three snapshot files for offline auditing and re-analysis:
      cars.json     — every CarSpec including ground-truth fields
      listings.json — every CarListing (asking, claimed cond/flags) + archetype
      sellers.json  — seller_id → archetype map (+ name/signature when curated)
    These exist independently of events.jsonl so analysts can join on
    car_id / listing_id / seller_id without parsing the streaming log."""
    cars_log = [
        {
            "car_id": c.car_id, "year": c.year, "make": c.make, "model": c.model,
            "body": c.body, "mileage": c.mileage,
            "true_condition": c.true_condition,
            "true_value": c.true_value,
            "seller_floor": c.seller_floor,
            "seller_ceiling": c.seller_ceiling,
            "true_vhr_flags": c.true_vhr_flags,
        }
        for c in cars_by_listing.values()
    ]
    listings_log = [
        {
            "listing_id": l.listing_id,
            "seller_id": l.seller_id,
            "seller_archetype": archetype_by_seller.get(l.seller_id, "?"),
            "car_id": l.car.car_id,
            "asking_price": l.asking_price,
            "listing_condition": l.listing_condition,
            "claimed_vhr_flags": l.claimed_vhr_flags,
            "asking_markup_over_true_value": l.asking_price / l.car.true_value,
        }
        for l in mp.listings.values()
    ]
    if seller_name_by_seller is not None:
        sellers_log: dict = {
            sid: {
                "archetype": archetype_by_seller.get(sid, "?"),
                "name": seller_name_by_seller.get(sid, sid),
                "signature_line": (seller_signature_by_seller or {}).get(sid, ""),
            }
            for sid in archetype_by_seller
        }
    else:
        sellers_log = archetype_by_seller
    (out_dir / "cars.json").write_text(json.dumps(cars_log, indent=2))
    (out_dir / "listings.json").write_text(json.dumps(listings_log, indent=2))
    (out_dir / "sellers.json").write_text(json.dumps(sellers_log, indent=2))


def run(cfg: S3Config) -> dict:
    rng = random.Random(cfg.seed)
    out_dir = Path(cfg.out_dir) / f"s3_seed{cfg.seed}_gamma{cfg.reputation_gamma}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "events.jsonl"

    # ---- LLM / replay mode setup ----
    cache = None
    generate_description = None
    buyer_message = None
    seller_message = None
    lookup_description = None
    lookup_buyer_message = None
    lookup_seller_message = None
    if cfg.mode in ("llm", "replay"):
        from ..llm_cache import LLMCache
        from ..descriptions import lookup_description
        from ..llm_agent import lookup_buyer_message, lookup_seller_message
        cache = LLMCache(Path(cfg.out_dir) / "llm_cache.jsonl")
        if cfg.mode == "llm":
            from ..descriptions import generate_description
            from ..llm_agent import buyer_message, seller_message

    # ---- Resolve sellers ----
    _seller_description_by_id: dict[str, str] = {}
    if cfg.sellers_source == "curated":
        from ..sellers import load_sellers
        seller_personas = load_sellers()           # 10 named SellerPersona
        seller_ids = [sp.seller_id for sp in seller_personas]
        archetypes_list = [sp.archetype for sp in seller_personas]
        seller_names = {sp.seller_id: sp.name for sp in seller_personas}
        seller_signatures = {sp.seller_id: sp.signature_line for sp in seller_personas}
        _seller_description_by_id = {sp.seller_id: sp.description for sp in seller_personas}
        k = len(seller_personas)
    else:
        archetypes_list = population_sample(seed=cfg.seed, k=cfg.k_sellers)
        seller_ids = [f"S_{i+1:02d}" for i in range(cfg.k_sellers)]
        seller_names = {sid: sid for sid in seller_ids}
        seller_signatures = {sid: "" for sid in seller_ids}
        k = cfg.k_sellers

    # ---- Resolve cars ----
    if cfg.cars_source == "curated":
        all_cars = load_curated_cars()       # 25 fixed CarSpec
        # Round-robin assign cars to sellers in order so each seller gets ~equal inventory.
        car_assignments: list[list] | None = [[] for _ in range(k)]
        for idx, c in enumerate(all_cars):
            car_assignments[idx % k].append(c)
    else:
        car_assignments = None    # signals: use generator per-seller

    mp = CarMarketplace(
        run_name=f"s3_seed{cfg.seed}_gamma{cfg.reputation_gamma}",
        reputation_gamma=cfg.reputation_gamma,
        log_path=log_path,
    )

    # ---- seed sellers + inventories ----
    sellers: dict[str, HeuristicSeller] = {}
    archetype_by_seller: dict[str, str] = {}
    seller_name_by_seller: dict[str, str] = {}
    seller_signature_by_seller: dict[str, str] = {}
    cars_by_listing: dict[str, "CarSpec"] = {}
    car_idx = 0
    for i, (sid, arch) in enumerate(zip(seller_ids, archetypes_list)):
        archetype_by_seller[sid] = arch.name
        seller_name_by_seller[sid] = seller_names[sid]
        seller_signature_by_seller[sid] = seller_signatures[sid]
        if car_assignments is not None:
            cars = car_assignments[i]
        else:
            n_inv = rng.randint(*cfg.inventory_per_seller)
            cars = generate(seed=cfg.seed * 1000 + i, n=n_inv)
        for c in cars:
            l = build_listing(
                c, arch, seller_id=sid,
                rng=random.Random(cfg.seed * 10000 + car_idx),
                listing_id=f"L_{car_idx+1:05d}",
            )
            mp.add_listing(l)
            if cfg.mode == "llm":
                l.description = generate_description(l, cache, model=cfg.llm_model)
            elif cfg.mode == "replay":
                desc = lookup_description(l, cache, model=cfg.llm_model)
                l.description = desc if desc is not None else ""
            cars_by_listing[l.listing_id] = c
            car_idx += 1
        sellers[sid] = HeuristicSeller(
            seller_id=sid, archetype=arch,
            rng=random.Random(cfg.seed * 100 + i),
        )

    def _bmsg(action: str, bid: float, listing_summary: str, persona) -> str:
        if cfg.mode == "fast" or cache is None:
            return f"(fast {action})"
        buyer_name = persona.name or persona.persona_id
        buyer_description = persona.description
        if cfg.mode == "llm":
            return buyer_message(buyer_name, buyer_description,
                                  listing_summary, action, bid, cache, model=cfg.llm_model)
        msg = lookup_buyer_message(buyer_name, buyer_description,
                                    listing_summary, action, bid, cache, model=cfg.llm_model)
        return msg if msg is not None else f"(replay-miss {action})"

    def _smsg(action: str, price: float, listing_summary: str, seller_id: str, archetype_name: str) -> str:
        if cfg.mode == "fast" or cache is None:
            return f"(fast {action})"
        name = seller_name_by_seller.get(seller_id, seller_id)
        sig = seller_signature_by_seller.get(seller_id, "")
        description = _seller_description_by_id.get(seller_id, "")
        if cfg.mode == "llm":
            return seller_message(name, description, sig, archetype_name,
                                    listing_summary, action, price, cache, model=cfg.llm_model)
        msg = lookup_seller_message(name, description, sig, archetype_name,
                                      listing_summary, action, price, cache, model=cfg.llm_model)
        return msg if msg is not None else f"(replay-miss {action})"

    def _summary(card) -> str:
        return f"{card.year} {card.make} {card.model} — {card.mileage}mi, cond {card.listing_condition:.1f}, asking ${card.asking_price:.0f}"

    # ---- snapshot the world BEFORE any negotiation, so post-hoc analysis
    #      can reconstruct the run and recompute regret/welfare offline ----
    _dump_snapshots(out_dir, mp, cars_by_listing, archetype_by_seller,
                    seller_name_by_seller, seller_signature_by_seller)

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
            off = mp.make_offer(buyer=buyer_id, listing_id=lid, price=bid, message=_bmsg("offer", bid, _summary(card), persona))
            if off is None:
                continue
            seller = sellers[card.seller_id]
            step = seller.respond_to_offer(
                car=car, asking_price=card.asking_price, offer_price=bid,
            )
            if step.action == "accept":
                d = mp.respond_to_offer(
                    seller=seller.seller_id, offer_id=off.offer_id,
                    action="accept", counter_price=None, message=_smsg("accept", bid, _summary(card), seller.seller_id, seller.archetype.name),
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
                    action="counter", counter_price=step.counter_price, message=_smsg("counter", step.counter_price, _summary(card), seller.seller_id, seller.archetype.name),
                )
                # Buyer evaluates counter as a new asking price. If her WTP >= counter,
                # she accepts by re-offering at the counter price.
                wtp_under_listing = buyer.propose_price(card, car) / 0.90
                if step.counter_price <= wtp_under_listing:
                    new_off = mp.make_offer(
                        buyer=buyer_id, listing_id=lid,
                        price=step.counter_price, message=_bmsg("accepts counter", step.counter_price, _summary(card), persona),
                    )
                    if new_off is not None:
                        d = mp.respond_to_offer(
                            seller=seller.seller_id, offer_id=new_off.offer_id,
                            action="accept", counter_price=None, message=_smsg("close", step.counter_price, _summary(card), seller.seller_id, seller.archetype.name),
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
        "k_sellers": k,                              # actual k resolved above
        "m_buyers_expected": cfg.m_buyers,
        "m_buyers_actual": buyers_processed,
        "deals": len(per_deal), "no_deal_buyers": no_deal_count,
        "listings_total": len(mp.listings),
        "listings_sold": sum(1 for l in mp.listings.values() if l.sold),
    }
    summary.update(run_metrics(per_deal, no_deal_count))
    (out_dir / "per_deal.json").write_text(json.dumps(per_deal, indent=2))
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary
