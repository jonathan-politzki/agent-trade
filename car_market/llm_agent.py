"""LLM-flavored negotiation messages via litellm. The DECISION
(accept/counter/decline, bid price) is taken by the heuristic policy in
policies.py; the LLM only writes the natural-language MESSAGE. This keeps
the ablation deterministic while making transcripts feel human."""
from __future__ import annotations

from litellm import completion

from .llm_cache import LLMCache
from .prompts import load_prompt

DEFAULT_MODEL = "anthropic/claude-haiku-4-5"


def buyer_message(buyer_name: str, buyer_description: str,
                   listing_summary: str, action: str, bid: float,
                   cache: LLMCache, model: str = DEFAULT_MODEL) -> str:
    ctx = {"who": "buyer", "name": buyer_name,
           "listing": listing_summary, "action": action,
           "bid": round(bid), "_model": model}
    hit = cache.get("negotiation_msg", ctx)
    if hit is not None:
        return hit
    prompt = load_prompt("buyer_message").format(
        buyer_name=buyer_name,
        buyer_description=buyer_description,
        listing_summary=listing_summary,
        action=action,
        bid=f"{bid:.0f}",
    )
    resp = completion(model=model, max_tokens=80,
                       messages=[{"role": "user", "content": prompt}])
    text = resp.choices[0].message.content.strip()
    cache.put("negotiation_msg", ctx, text)
    return text


def seller_message(seller_name: str, description: str, signature_line: str,
                    archetype_name: str, listing_summary: str,
                    action: str, price: float,
                    cache: LLMCache, model: str = DEFAULT_MODEL) -> str:
    ctx = {"who": "seller", "name": seller_name, "archetype": archetype_name,
           "listing": listing_summary, "action": action,
           "price": round(price), "_model": model}
    hit = cache.get("negotiation_msg", ctx)
    if hit is not None:
        return hit
    prompt = load_prompt("seller_message").format(
        seller_name=seller_name,
        description=description,
        signature_line=signature_line,
        listing_summary=listing_summary,
        action=action,
        price=f"{price:.0f}",
    )
    resp = completion(model=model, max_tokens=80,
                       messages=[{"role": "user", "content": prompt}])
    text = resp.choices[0].message.content.strip()
    cache.put("negotiation_msg", ctx, text)
    return text


def lookup_buyer_message(buyer_name: str, buyer_description: str,
                          listing_summary: str, action: str, bid: float,
                          cache: LLMCache, model: str = DEFAULT_MODEL) -> str | None:
    """Cache-only lookup — returns None on miss. No API call."""
    ctx = {"who": "buyer", "name": buyer_name,
           "listing": listing_summary, "action": action,
           "bid": round(bid), "_model": model}
    return cache.get("negotiation_msg", ctx)


def lookup_seller_message(seller_name: str, description: str, signature_line: str,
                           archetype_name: str, listing_summary: str,
                           action: str, price: float,
                           cache: LLMCache, model: str = DEFAULT_MODEL) -> str | None:
    """Cache-only lookup — returns None on miss. No API call."""
    ctx = {"who": "seller", "name": seller_name, "archetype": archetype_name,
           "listing": listing_summary, "action": action,
           "price": round(price), "_model": model}
    return cache.get("negotiation_msg", ctx)
