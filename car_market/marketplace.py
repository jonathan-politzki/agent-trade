"""Car marketplace extending the Project Deal substrate with:
- private car_spec attached to each listing
- per-seller Beta reputation
- listing locks while an offer is open
- single-open-offer-per-buyer rule
- search() with relevance × reputation ranking
- lookup_seller() for instrumentation
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from .archetypes import CarListing
from .reputation import BetaReputation, update_on_deal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Offer:
    offer_id: str
    listing_id: str
    buyer: str
    seller: str
    price: float
    message: str
    status: str = "open"


@dataclass
class Deal:
    deal_id: str
    listing_id: str
    seller: str
    buyer: str
    price: float
    timestamp: str
    true_value: float
    listing_condition: float
    true_condition: float


@dataclass
class ListingCard:
    """Public listing summary returned by search()."""
    listing_id: str
    seller_id: str
    year: int
    make: str
    model: str
    body: str
    mileage: int
    listing_condition: float
    asking_price: float
    seller_stars: float       # 0.0 in hidden mode


@dataclass
class SellerCard:
    """Public seller info returned by lookup_seller()."""
    seller_id: str
    stars: float
    review_count: int
    excerpts: list[str]


class CarMarketplace:
    def __init__(self, run_name: str, reputation_gamma: float = 0.5,
                 log_path: Path | None = None):
        self.run_name = run_name
        self.reputation_gamma = reputation_gamma
        self.listings: dict[str, CarListing] = {}
        self.offers: dict[str, Offer] = {}
        self.deals: list[Deal] = []
        self.reputation: dict[str, BetaReputation] = {}
        self._listing_locked: set[str] = set()
        self._buyer_open_offer: dict[str, str] = {}
        self._offer_counter = 0
        self._deal_counter = 0
        self.log_path = log_path
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("")

    # ---- listings -----------------------------------------------------------

    def add_listing(self, listing: CarListing) -> None:
        self.listings[listing.listing_id] = listing
        self.reputation.setdefault(listing.seller_id, BetaReputation(listing.seller_id))
        self._emit({
            "kind": "listing", "listing_id": listing.listing_id,
            "seller_id": listing.seller_id, "car_id": listing.car.car_id,
            "asking_price": listing.asking_price,
            "listing_condition": listing.listing_condition,
            "claimed_vhr_flags": listing.claimed_vhr_flags,
            "true_condition_ground_truth": listing.car.true_condition,
            "true_value_ground_truth": listing.car.true_value,
        })

    # ---- search & lookup ----------------------------------------------------

    def search(self, query: str, max_results: int = 10) -> list[ListingCard]:
        q = query.lower()
        scored = []
        for l in self.listings.values():
            if l.sold or l.listing_id in self._listing_locked:
                continue
            relevance = 0.5
            tokens = q.split()
            for t in tokens:
                if t in l.car.body.lower() or t in l.car.make.lower() or t in l.car.model.lower():
                    relevance = 1.0
                    break
            rating_norm = (self.reputation[l.seller_id].mean_rating() - 0.5) * 2.0
            score = relevance * (1.0 + self.reputation_gamma * rating_norm)
            scored.append((score, l))
        scored.sort(key=lambda x: (-x[0], x[1].listing_id))
        out: list[ListingCard] = []
        for _, l in scored[:max_results]:
            rep = self.reputation[l.seller_id]
            out.append(ListingCard(
                listing_id=l.listing_id, seller_id=l.seller_id,
                year=l.car.year, make=l.car.make, model=l.car.model,
                body=l.car.body, mileage=l.car.mileage,
                listing_condition=l.listing_condition,
                asking_price=l.asking_price,
                seller_stars=rep.stars() if self.reputation_gamma > 0 else 0.0,
            ))
        return out

    def lookup_seller(self, seller_id: str) -> SellerCard | None:
        if self.reputation_gamma == 0.0:
            return None
        rep = self.reputation.get(seller_id)
        if rep is None:
            return None
        return SellerCard(
            seller_id=seller_id, stars=rep.stars(),
            review_count=rep.review_count, excerpts=list(rep.excerpts),
        )

    # ---- offers -------------------------------------------------------------

    def make_offer(self, buyer: str, listing_id: str, price: float, message: str) -> Offer | None:
        l = self.listings.get(listing_id)
        if l is None or l.sold or listing_id in self._listing_locked:
            return None
        if buyer in self._buyer_open_offer:
            return None
        if l.seller_id == buyer:
            return None
        self._offer_counter += 1
        off = Offer(
            offer_id=f"O_{self._offer_counter:05d}",
            listing_id=listing_id, buyer=buyer, seller=l.seller_id,
            price=float(price), message=message,
        )
        self.offers[off.offer_id] = off
        self._listing_locked.add(listing_id)
        self._buyer_open_offer[buyer] = off.offer_id
        self._emit({"kind": "offer", "offer_id": off.offer_id, "listing_id": listing_id,
                     "buyer": buyer, "seller": l.seller_id, "price": float(price)})
        return off

    def respond_to_offer(self, seller: str, offer_id: str, action: str,
                          counter_price: float | None, message: str) -> Deal | None:
        off = self.offers.get(offer_id)
        if off is None or off.status != "open" or off.seller != seller:
            return None
        l = self.listings[off.listing_id]

        if action == "accept":
            return self._settle(off, off.price)
        if action == "decline":
            off.status = "declined"
            self._release(off.listing_id, off.buyer)
            self._emit({"kind": "decline", "offer_id": offer_id})
            return None
        if action == "counter" and counter_price is not None:
            off.status = "withdrawn"
            self._release(off.listing_id, off.buyer)
            self._emit({"kind": "counter", "offer_id": offer_id,
                         "counter_price": float(counter_price)})
            return None
        return None

    def buyer_withdraw(self, buyer: str) -> None:
        oid = self._buyer_open_offer.get(buyer)
        if not oid:
            return
        off = self.offers[oid]
        if off.status == "open":
            off.status = "withdrawn"
            self._release(off.listing_id, buyer)
            self._emit({"kind": "withdraw", "offer_id": oid, "buyer": buyer})

    def timeout_offer(self, offer_id: str) -> None:
        off = self.offers.get(offer_id)
        if off and off.status == "open":
            off.status = "timeout"
            self._release(off.listing_id, off.buyer)
            self._emit({"kind": "timeout", "offer_id": offer_id})

    # ---- settlement ---------------------------------------------------------

    def _settle(self, off: Offer, price: float) -> Deal:
        l = self.listings[off.listing_id]
        l.sold = True
        off.status = "accepted"
        self._deal_counter += 1
        deal = Deal(
            deal_id=f"D_{self._deal_counter:05d}",
            listing_id=off.listing_id, seller=off.seller, buyer=off.buyer,
            price=price, timestamp=_now_iso(),
            true_value=l.car.true_value,
            listing_condition=l.listing_condition,
            true_condition=l.car.true_condition,
        )
        self.deals.append(deal)
        update_on_deal(
            self.reputation[off.seller],
            listing_cond=l.listing_condition,
            true_cond=l.car.true_condition,
        )
        for o in list(self.offers.values()):
            if o.listing_id == off.listing_id and o.offer_id != off.offer_id and o.status == "open":
                o.status = "withdrawn"
                self._release(o.listing_id, o.buyer)
        self._release(off.listing_id, off.buyer)
        self._emit({"kind": "deal", "deal_id": deal.deal_id, **asdict(deal)})
        return deal

    def _release(self, listing_id: str, buyer: str) -> None:
        self._listing_locked.discard(listing_id)
        if self._buyer_open_offer.get(buyer) is not None:
            cur = self.offers.get(self._buyer_open_offer[buyer])
            if cur is None or cur.listing_id != listing_id or cur.status != "open":
                self._buyer_open_offer.pop(buyer, None)

    # ---- logging ------------------------------------------------------------

    def _emit(self, event: dict) -> None:
        event = {"run": self.run_name, "timestamp": _now_iso(), **event}
        if self.log_path:
            with self.log_path.open("a") as f:
                f.write(json.dumps(event, default=str) + "\n")
