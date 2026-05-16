"""Tool schemas for the buyer and seller agents.

One tool call per turn. Conversation turns through a tight FSM:
  - seller opens with pitch (turn 0)
  - buyer responds (ask / inspect / offer / accept / walk_away / chat)
  - seller responds (respond / counter / accept / decline / walk_away / chat)
  - ...until terminal state.
"""
from __future__ import annotations

from .car import FOCUS_AREAS


# Seller tools.
SELLER_TOOLS = [
    {
        "name": "pitch",
        "description": "Open the conversation with your sales pitch. Use only on the very first turn.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string", "description": "Opening pitch — 1-4 sentences."}},
            "required": ["message"],
        },
    },
    {
        "name": "respond",
        "description": "Free-form response to the buyer's latest message (answer a question, discuss the car, build rapport). Use this when the buyer asked something and you do NOT want to change the price or close the deal yet.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
    {
        "name": "counter_offer",
        "description": "Make or counter a price offer. Use when you want to move the headline price.",
        "input_schema": {
            "type": "object",
            "properties": {
                "price": {"type": "number"},
                "message": {"type": "string"},
            },
            "required": ["price", "message"],
        },
    },
    {
        "name": "accept_offer",
        "description": "Accept the buyer's most recent price offer and close the deal.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
    {
        "name": "decline_offer",
        "description": "Decline the buyer's most recent price offer without making a counter. Conversation continues.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
    {
        "name": "walk_away",
        "description": "End the conversation without a sale. Use only if the buyer is asking you to violate your principles or the negotiation is clearly stuck below your reservation price.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
]


BUYER_TOOLS = [
    {
        "name": "ask",
        "description": "Ask the seller a question about the car (history, condition, maintenance, anything). Free-form.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
    {
        "name": "request_inspection",
        "description": (
            "Pay for an independent inspection that truthfully reveals private facts about a specific focus area. "
            f"focus_area must be one of: {list(FOCUS_AREAS)}. Each inspection costs the inspection fee in your config "
            "and may surface defects the seller did not disclose."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"focus_area": {"type": "string", "enum": list(FOCUS_AREAS)}},
            "required": ["focus_area"],
        },
    },
    {
        "name": "make_offer",
        "description": "Make a price offer to the seller. The seller will accept, counter, or decline. Must be within your budget.",
        "input_schema": {
            "type": "object",
            "properties": {
                "price": {"type": "number"},
                "message": {"type": "string"},
            },
            "required": ["price", "message"],
        },
    },
    {
        "name": "accept_seller_price",
        "description": "Accept the seller's most recent stated price (or the original asking price if no counter has been made) and close the deal.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
    {
        "name": "walk_away",
        "description": "End the conversation without buying. Use when you do not trust the seller, the price exceeds your budget, or the car is wrong for you.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
]
