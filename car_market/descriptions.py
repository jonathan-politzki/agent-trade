"""LLM-generated listing prose via litellm. Conditioned on the seller's
CLAIMS (listing_condition, claimed_vhr_flags), not the true state. Cached.

Provider selection via model string: 'anthropic/claude-haiku-4-5',
'openai/gpt-4o-mini', 'gemini/gemini-2.0-flash', etc."""
from __future__ import annotations

from litellm import completion

from .archetypes import CarListing
from .llm_cache import LLMCache
from .prompts import load_prompt

DEFAULT_MODEL = "anthropic/claude-haiku-4-5"


def generate_description(listing: CarListing, cache: LLMCache,
                          model: str = DEFAULT_MODEL) -> str:
    ctx = {
        "year": listing.car.year, "make": listing.car.make,
        "model": listing.car.model, "body": listing.car.body,
        "mileage": listing.car.mileage,
        "listing_condition": round(listing.listing_condition, 1),
        "claimed_vhr_flags": sorted(listing.claimed_vhr_flags),
        "asking_price": round(listing.asking_price),
        "_model": model,
    }
    hit = cache.get("description", ctx)
    if hit is not None:
        return hit
    template = load_prompt("listing_description")
    prompt = template.format(
        year=ctx['year'], make=ctx['make'], model=ctx['model'], body=ctx['body'],
        mileage=ctx['mileage'], asking_price=ctx['asking_price'],
        listing_condition=ctx['listing_condition'],
        claimed_vhr_flags_joined=', '.join(ctx['claimed_vhr_flags']),
    )
    resp = completion(
        model=model, max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    cache.put("description", ctx, text)
    return text


def lookup_description(listing: CarListing, cache: LLMCache,
                        model: str = DEFAULT_MODEL) -> str | None:
    """Cache-only lookup — returns None on miss. No API call."""
    ctx = {
        "year": listing.car.year, "make": listing.car.make,
        "model": listing.car.model, "body": listing.car.body,
        "mileage": listing.car.mileage,
        "listing_condition": round(listing.listing_condition, 1),
        "claimed_vhr_flags": sorted(listing.claimed_vhr_flags),
        "asking_price": round(listing.asking_price),
        "_model": model,
    }
    return cache.get("description", ctx)
