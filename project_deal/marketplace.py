"""Marketplace state: listings, offers, deals, and the public message log.

This is the analog of the experiment's shared Slack channel — every agent reads
the same public history and the same set of open listings/offers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _short_id(prefix: str, n: int) -> str:
    return f"{prefix}_{n:04d}"


@dataclass
class Listing:
    listing_id: str
    seller: str
    item: str
    asking_price: float
    description: str
    sold: bool = False


@dataclass
class Offer:
    offer_id: str
    listing_id: str
    buyer: str
    seller: str
    price: float
    message: str
    status: str = "open"  # open | accepted | declined | countered | withdrawn


@dataclass
class Deal:
    deal_id: str
    listing_id: str
    item: str
    seller: str
    buyer: str
    price: float
    timestamp: str


@dataclass
class Event:
    """A single line in the shared channel. Everyone sees these."""
    kind: str            # listing | offer | counter | accept | decline | message | system
    actor: str
    text: str
    ref: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=_now_iso)


class Marketplace:
    def __init__(self, run_name: str, log_path: Path | None = None):
        self.run_name = run_name
        self.listings: dict[str, Listing] = {}
        self.offers: dict[str, Offer] = {}
        self.deals: list[Deal] = []
        self.events: list[Event] = []
        self._listing_counter = 0
        self._offer_counter = 0
        self._deal_counter = 0
        self.log_path = log_path
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("")

    # ---- mutations ----------------------------------------------------------

    def list_item(self, seller: str, item: str, asking_price: float, description: str) -> Listing:
        self._listing_counter += 1
        lst = Listing(
            listing_id=_short_id("L", self._listing_counter),
            seller=seller,
            item=item,
            asking_price=float(asking_price),
            description=description,
        )
        self.listings[lst.listing_id] = lst
        self._emit(Event(
            kind="listing", actor=seller,
            text=f"LISTED {lst.listing_id}: {item} — ${asking_price:.2f}. {description}",
            ref={"listing_id": lst.listing_id},
        ))
        return lst

    def make_offer(self, buyer: str, listing_id: str, price: float, message: str) -> Offer | None:
        lst = self.listings.get(listing_id)
        if not lst or lst.sold or lst.seller == buyer:
            return None
        self._offer_counter += 1
        off = Offer(
            offer_id=_short_id("O", self._offer_counter),
            listing_id=listing_id,
            buyer=buyer,
            seller=lst.seller,
            price=float(price),
            message=message,
        )
        self.offers[off.offer_id] = off
        self._emit(Event(
            kind="offer", actor=buyer,
            text=f"OFFER {off.offer_id} on {listing_id} ({lst.item}): ${price:.2f} from {buyer} to {lst.seller}. {message}",
            ref={"offer_id": off.offer_id, "listing_id": listing_id},
        ))
        return off

    def respond_to_offer(self, seller: str, offer_id: str, action: str,
                         counter_price: float | None, message: str) -> Deal | Offer | None:
        off = self.offers.get(offer_id)
        if not off or off.status != "open" or off.seller != seller:
            return None
        lst = self.listings.get(off.listing_id)
        if not lst or lst.sold:
            return None

        if action == "accept":
            off.status = "accepted"
            lst.sold = True
            self._deal_counter += 1
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            deal = Deal(
                deal_id=f"deal_{today}_{off.seller}_{off.buyer}_{self._deal_counter:03d}",
                listing_id=lst.listing_id, item=lst.item,
                seller=off.seller, buyer=off.buyer,
                price=off.price, timestamp=_now_iso(),
            )
            self.deals.append(deal)
            for other_id, other in list(self.offers.items()):
                if other.listing_id == lst.listing_id and other.status == "open" and other_id != offer_id:
                    other.status = "withdrawn"
            self._emit(Event(
                kind="accept", actor=seller,
                text=f"ACCEPTED {offer_id}. DEAL {deal.deal_id}: {lst.item} sold to {off.buyer} for ${off.price:.2f}. {message}",
                ref={"deal_id": deal.deal_id, "offer_id": offer_id, "listing_id": lst.listing_id},
            ))
            return deal

        if action == "decline":
            off.status = "declined"
            self._emit(Event(
                kind="decline", actor=seller,
                text=f"DECLINED {offer_id} on {lst.listing_id} ({lst.item}). {message}",
                ref={"offer_id": offer_id, "listing_id": lst.listing_id},
            ))
            return off

        if action == "counter" and counter_price is not None:
            off.status = "countered"
            self._offer_counter += 1
            new_off = Offer(
                offer_id=_short_id("O", self._offer_counter),
                listing_id=lst.listing_id,
                buyer=off.buyer, seller=off.seller,
                price=float(counter_price),
                message=f"(counter to {offer_id}) {message}",
            )
            self.offers[new_off.offer_id] = new_off
            self._emit(Event(
                kind="counter", actor=seller,
                text=f"COUNTER on {offer_id}: new offer {new_off.offer_id} at ${counter_price:.2f} from {seller}. {message}",
                ref={"offer_id": new_off.offer_id, "listing_id": lst.listing_id, "prev_offer_id": offer_id},
            ))
            return new_off

        return None

    def send_message(self, actor: str, message: str) -> None:
        self._emit(Event(kind="message", actor=actor, text=message))

    # ---- views --------------------------------------------------------------

    def recent_events_text(self, limit: int) -> str:
        if not self.events:
            return "(channel is empty)"
        tail = self.events[-limit:]
        return "\n".join(f"[{e.timestamp[-8:]}] {e.actor}: {e.text}" for e in tail)

    def open_listings_text(self, exclude_seller: str | None = None) -> str:
        rows = []
        for lst in self.listings.values():
            if lst.sold:
                continue
            if exclude_seller and lst.seller == exclude_seller:
                continue
            rows.append(f"  {lst.listing_id} (seller={lst.seller}): {lst.item} — asking ${lst.asking_price:.2f}. {lst.description}")
        return "\n".join(rows) if rows else "  (none)"

    def open_offers_for(self, seller: str) -> str:
        rows = []
        for off in self.offers.values():
            if off.status != "open" or off.seller != seller:
                continue
            lst = self.listings[off.listing_id]
            rows.append(f"  {off.offer_id} on {off.listing_id} ({lst.item}, asked ${lst.asking_price:.2f}): ${off.price:.2f} from {off.buyer}. \"{off.message}\"")
        return "\n".join(rows) if rows else "  (none)"

    def my_listings(self, seller: str) -> str:
        rows = []
        for lst in self.listings.values():
            if lst.seller != seller:
                continue
            tag = "SOLD" if lst.sold else "open"
            rows.append(f"  {lst.listing_id} [{tag}]: {lst.item} — asking ${lst.asking_price:.2f}")
        return "\n".join(rows) if rows else "  (none)"

    # ---- persistence --------------------------------------------------------

    def _emit(self, ev: Event) -> None:
        self.events.append(ev)
        if self.log_path:
            with self.log_path.open("a") as f:
                f.write(json.dumps({"run": self.run_name, **asdict(ev)}) + "\n")

    def snapshot(self) -> dict:
        return {
            "run": self.run_name,
            "listings": [asdict(v) for v in self.listings.values()],
            "offers": [asdict(v) for v in self.offers.values()],
            "deals": [asdict(v) for v in self.deals],
            "n_events": len(self.events),
        }
