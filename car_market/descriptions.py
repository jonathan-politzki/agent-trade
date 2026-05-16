"""LLM-generated listing prose via litellm. Conditioned on the seller's
CLAIMS (listing_condition, claimed_vhr_flags), not the true state. Cached.

Provider selection via model string: 'anthropic/claude-haiku-4-5',
'openai/gpt-4o-mini', 'gemini/gemini-2.0-flash', etc."""
from __future__ import annotations

from litellm import completion

from .archetypes import CarListing
from .llm_cache import LLMCache

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
    prompt = f"""\
You are a used-car salesperson writing a listing description for AutoTrader.
Write 3 short sentences, casual but professional, that emphasise the positives.
Do NOT mention the listing condition number directly; describe it in words.

Vehicle: {ctx['year']} {ctx['make']} {ctx['model']} ({ctx['body']})
Mileage: {ctx['mileage']}
Asking: ${ctx['asking_price']}
Condition (1-5 scale, seller's claim): {ctx['listing_condition']}
Vehicle history flags: {', '.join(ctx['claimed_vhr_flags'])}
"""
    resp = completion(
        model=model, max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    cache.put("description", ctx, text)
    return text
