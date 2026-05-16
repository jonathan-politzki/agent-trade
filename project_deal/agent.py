"""One agent turn: build context, call Claude with tool use, apply the action.

The agent picks exactly one action per turn — list an item, make an offer,
respond to an open offer, send a message, or pass. This mirrors the
description in the experiment writeup: 'post an item for sale, make an offer
for someone else's goods, or seal a deal.'
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from anthropic import Anthropic

from .marketplace import Marketplace


TOOLS = [
    {
        "name": "list_item",
        "description": "List one of your own items for sale in the marketplace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item": {"type": "string", "description": "Name of the item."},
                "asking_price": {"type": "number", "description": "Your asking price in USD."},
                "description": {"type": "string", "description": "Short description, condition, notes."},
            },
            "required": ["item", "asking_price", "description"],
        },
    },
    {
        "name": "make_offer",
        "description": "Make a bid on another participant's open listing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "listing_id": {"type": "string", "description": "ID of the listing, e.g. L_0003."},
                "price": {"type": "number", "description": "Offered price in USD."},
                "message": {"type": "string", "description": "Short note to the seller."},
            },
            "required": ["listing_id", "price", "message"],
        },
    },
    {
        "name": "respond_to_offer",
        "description": "Accept, counter, or decline an open offer on one of your listings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_id": {"type": "string", "description": "ID of the offer, e.g. O_0007."},
                "action": {"type": "string", "enum": ["accept", "counter", "decline"]},
                "counter_price": {"type": "number", "description": "Required if action=counter."},
                "message": {"type": "string", "description": "Short note to the buyer."},
            },
            "required": ["offer_id", "action", "message"],
        },
    },
    {
        "name": "send_message",
        "description": "Post a public message to the channel (e.g. clarifying questions, social signal). Use sparingly.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
    {
        "name": "pass_turn",
        "description": "Skip this turn — useful if you have no good move right now.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


@dataclass
class Participant:
    name: str
    model: str
    system_prompt: str
    budget_remaining: float


def _user_context(p: Participant, mp: Marketplace) -> str:
    return f"""\
You are {p.name}'s agent in a closed marketplace experiment.

Your remaining budget: ${p.budget_remaining:.2f}
Your active/sold listings:
{mp.my_listings(p.name)}

Open listings from other participants:
{mp.open_listings_text(exclude_seller=p.name)}

Open offers on YOUR listings (you must respond to these to make a deal):
{mp.open_offers_for(p.name)}

Recent channel activity (most recent last):
{mp.recent_events_text(30)}

It is now your turn. Pick exactly ONE tool call. Prefer concrete trading
actions (list_item, make_offer, respond_to_offer) over chat. Do not exceed
your budget when making offers. Listings and offers are public — every
participant sees them.
"""


def run_turn(client: Anthropic, p: Participant, mp: Marketplace, max_tokens: int = 1024) -> dict:
    """Run one turn for participant p. Returns a dict describing what happened."""
    resp = client.messages.create(
        model=p.model,
        max_tokens=max_tokens,
        system=p.system_prompt,
        tools=TOOLS,
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": _user_context(p, mp)}],
    )

    tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
    if tool_use is None:
        return {"actor": p.name, "model": p.model, "action": "no_tool"}

    name = tool_use.name
    args = tool_use.input or {}
    result: dict = {"actor": p.name, "model": p.model, "action": name, "args": args}

    if name == "list_item":
        lst = mp.list_item(
            seller=p.name,
            item=args.get("item", "unnamed"),
            asking_price=float(args.get("asking_price", 0)),
            description=args.get("description", ""),
        )
        result["listing_id"] = lst.listing_id
        return result

    if name == "make_offer":
        price = float(args.get("price", 0))
        if price > p.budget_remaining + 1e-6:
            mp.send_message(p.name, f"(skipped offer — over budget; have ${p.budget_remaining:.2f})")
            result["skipped"] = "over_budget"
            return result
        off = mp.make_offer(
            buyer=p.name,
            listing_id=args.get("listing_id", ""),
            price=price,
            message=args.get("message", ""),
        )
        result["offer_id"] = off.offer_id if off else None
        return result

    if name == "respond_to_offer":
        out = mp.respond_to_offer(
            seller=p.name,
            offer_id=args.get("offer_id", ""),
            action=args.get("action", "decline"),
            counter_price=(float(args["counter_price"]) if "counter_price" in args and args["counter_price"] is not None else None),
            message=args.get("message", ""),
        )
        if hasattr(out, "deal_id"):
            result["deal_id"] = out.deal_id  # type: ignore[attr-defined]
        return result

    if name == "send_message":
        mp.send_message(p.name, args.get("message", ""))
        return result

    if name == "pass_turn":
        mp.send_message(p.name, "(passes)")
        return result

    return result
