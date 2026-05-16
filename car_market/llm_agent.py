"""LLM-flavored negotiation messages via litellm. The DECISION
(accept/counter/decline, bid price) is taken by the heuristic policy in
policies.py; the LLM only writes the natural-language MESSAGE. This keeps
the ablation deterministic while making transcripts feel human."""
from __future__ import annotations

from litellm import completion

from .llm_cache import LLMCache

DEFAULT_MODEL = "anthropic/claude-haiku-4-5"


def buyer_message(buyer_persona_id: str, listing_summary: str,
                   action: str, bid: float, cache: LLMCache,
                   model: str = DEFAULT_MODEL) -> str:
    ctx = {"who": "buyer", "persona": buyer_persona_id,
           "listing": listing_summary, "action": action,
           "bid": round(bid), "_model": model}
    hit = cache.get("negotiation_msg", ctx)
    if hit is not None:
        return hit
    prompt = f"""\
You are a buyer ({buyer_persona_id}) negotiating for a used car on a dealer
website. Write ONE short conversational sentence (max 25 words) that goes
with this action. Be in-character for the persona.

Listing: {listing_summary}
Your action: {action}
Your bid: ${bid:.0f}
"""
    resp = completion(model=model, max_tokens=80,
                       messages=[{"role": "user", "content": prompt}])
    text = resp.choices[0].message.content.strip()
    cache.put("negotiation_msg", ctx, text)
    return text


def seller_message(archetype_name: str, listing_summary: str,
                    action: str, price: float, cache: LLMCache,
                    model: str = DEFAULT_MODEL) -> str:
    ctx = {"who": "seller", "archetype": archetype_name,
           "listing": listing_summary, "action": action,
           "price": round(price), "_model": model}
    hit = cache.get("negotiation_msg", ctx)
    if hit is not None:
        return hit
    prompt = f"""\
You are a used-car seller with the '{archetype_name}' persona (honest /
moderate / aggressive). Write ONE short conversational sentence (max 25
words) to accompany this action.

Listing: {listing_summary}
Your action: {action}
Price involved: ${price:.0f}
"""
    resp = completion(model=model, max_tokens=80,
                       messages=[{"role": "user", "content": prompt}])
    text = resp.choices[0].message.content.strip()
    cache.put("negotiation_msg", ctx, text)
    return text


def lookup_buyer_message(buyer_persona_id: str, listing_summary: str,
                          action: str, bid: float, cache: LLMCache,
                          model: str = DEFAULT_MODEL) -> str | None:
    """Cache-only lookup — returns None on miss. No API call."""
    ctx = {"who": "buyer", "persona": buyer_persona_id,
           "listing": listing_summary, "action": action,
           "bid": round(bid), "_model": model}
    return cache.get("negotiation_msg", ctx)


def lookup_seller_message(archetype_name: str, listing_summary: str,
                           action: str, price: float, cache: LLMCache,
                           model: str = DEFAULT_MODEL) -> str | None:
    """Cache-only lookup — returns None on miss. No API call."""
    ctx = {"who": "seller", "archetype": archetype_name,
           "listing": listing_summary, "action": action,
           "price": round(price), "_model": model}
    return cache.get("negotiation_msg", ctx)
