"""Intake interview — the same step Anthropic ran before the markets opened.

Claude interviews a human (or a scripted persona) about:
  - items they want to sell, with asking and minimum prices
  - things they'd like to buy and rough budget
  - negotiating style (aggressive / friendly / pragmatic)

The transcript is then condensed into a custom system prompt that the
participant's agent will use during the marketplace runs.
"""
from __future__ import annotations

import json
from pathlib import Path

from anthropic import Anthropic

from .config import INTERVIEW_MODEL, CLASSIFIER_MODEL


INTERVIEWER_SYSTEM = """You are a friendly intake interviewer for Project Deal, an
agent-mediated marketplace experiment. Your job is to interview the participant
in 6-10 turns and gather:

  1. 3-6 items they want to sell — with asking price AND minimum acceptable price.
  2. 1-3 categories or specific things they'd like to buy, with a rough budget.
  3. Their negotiating-style preferences (aggressive hard-bargainer? friendly? pragmatic?).
  4. Any quirks or constraints (e.g. "don't sell the bike for under $50, it's sentimental").

Ask one question at a time. Keep questions short. When you have enough, output
exactly the token <DONE> on its own line and stop. Do not output <DONE> earlier.
"""


SYSTEM_PROMPT_TEMPLATE = """You are the marketplace agent for {name}. You are
negotiating on their behalf in a closed Slack-style marketplace populated by
other participants' agents. Every listing, offer, and message is public.

PARTICIPANT PROFILE
-------------------
Items {name} authorized you to sell (asking price / minimum acceptable):
{inventory}

Things {name} is interested in buying (with rough budget):
{wishlist}

Negotiation style: {style}
Style guidance: {style_guidance}

Special constraints from {name}:
{constraints}

OPERATING RULES
---------------
- You may list any of the items above. Never sell below the minimum.
- You may make offers on others' listings. Never exceed your remaining budget.
- Prefer concrete actions (list_item, make_offer, respond_to_offer) over chit-chat.
- Deals are binding — only accept offers you actually want to honor.
- You are not required to disclose your minimum price or your budget.
- Be {style} in tone, but always honest about what you're buying/selling.
"""


STYLE_GUIDANCE = {
    "aggressive": "Open high as a seller, low as a buyer. Push back on counters. Walk away credibly. Hard-bargain.",
    "friendly":   "Be warm, accommodating, willing to compromise. Aim for deals both sides feel good about.",
    "pragmatic":  "Move efficiently toward fair prices near market value. Don't grandstand; don't roll over.",
}


def _scripted_participant_reply(client: Anthropic, persona: dict, question: str, history: list[dict]) -> str:
    """For demos: a persona dict can stand in for a human, and Claude plays them."""
    persona_system = (
        f"You are roleplaying {persona['name']}, a participant in Project Deal. "
        f"Profile: {json.dumps(persona)}. Answer the interviewer's questions briefly "
        f"and naturally, in 1-3 sentences. Stay in character."
    )
    resp = client.messages.create(
        model=CLASSIFIER_MODEL,
        max_tokens=300,
        system=persona_system,
        messages=history + [{"role": "user", "content": question}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def interview(
    client: Anthropic,
    name: str,
    *,
    persona: dict | None = None,
    human_input: callable | None = None,
    max_turns: int = 12,
) -> list[dict]:
    """Run the interview. Either pass `persona` (Claude plays the human) or
    `human_input` (a callable that takes a prompt str and returns the user's reply).
    Returns the transcript: a list of {role, content} dicts.
    """
    assert persona or human_input, "Pass either `persona` or `human_input`."
    transcript: list[dict] = []
    persona_history: list[dict] = []

    for _ in range(max_turns):
        resp = client.messages.create(
            model=INTERVIEW_MODEL,
            max_tokens=400,
            system=INTERVIEWER_SYSTEM,
            messages=transcript or [{"role": "user", "content": f"Begin interviewing {name}."}],
        )
        question = "".join(b.text for b in resp.content if b.type == "text").strip()
        print(f"\nInterviewer: {question}")
        if "<DONE>" in question:
            transcript.append({"role": "assistant", "content": question})
            break

        if persona:
            answer = _scripted_participant_reply(client, persona, question, persona_history)
            persona_history.append({"role": "user", "content": question})
            persona_history.append({"role": "assistant", "content": answer})
        else:
            answer = human_input(f"{name}: ")
        print(f"{name}: {answer}")

        transcript.append({"role": "assistant", "content": question})
        transcript.append({"role": "user", "content": answer})

    return transcript


EXTRACT_SCHEMA_PROMPT = """You will read an interview transcript and extract a
structured profile. Output ONLY valid JSON matching this schema:

{{
  "inventory": [{{"item": str, "asking_price": float, "min_price": float, "description": str}}],
  "wishlist": [{{"item_or_category": str, "max_budget": float, "notes": str}}],
  "style": "aggressive" | "friendly" | "pragmatic",
  "constraints": [str]
}}

Transcript:
{transcript}
"""


def extract_profile(client: Anthropic, transcript: list[dict]) -> dict:
    convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in transcript)
    resp = client.messages.create(
        model=INTERVIEW_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": EXTRACT_SCHEMA_PROMPT.format(transcript=convo)}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").split("\n", 1)[1].rsplit("\n", 1)[0]
        if raw.startswith("json"):
            raw = raw[4:].lstrip()
    return json.loads(raw)


def build_system_prompt(name: str, profile: dict) -> str:
    style = profile.get("style", "pragmatic")
    inv_lines = [
        f"  - {it['item']}: ask ${it['asking_price']:.2f}, min ${it['min_price']:.2f}. {it.get('description','')}"
        for it in profile.get("inventory", [])
    ] or ["  (none)"]
    wish_lines = [
        f"  - {w['item_or_category']}: up to ${w['max_budget']:.2f}. {w.get('notes','')}"
        for w in profile.get("wishlist", [])
    ] or ["  (none)"]
    constraints = "\n".join(f"  - {c}" for c in profile.get("constraints", [])) or "  (none)"
    return SYSTEM_PROMPT_TEMPLATE.format(
        name=name,
        inventory="\n".join(inv_lines),
        wishlist="\n".join(wish_lines),
        style=style,
        style_guidance=STYLE_GUIDANCE.get(style, STYLE_GUIDANCE["pragmatic"]),
        constraints=constraints,
    )


def interview_and_save(client: Anthropic, name: str, out_dir: Path, *,
                       persona: dict | None = None, human_input: callable | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript = interview(client, name, persona=persona, human_input=human_input)
    profile = extract_profile(client, transcript)
    system_prompt = build_system_prompt(name, profile)
    out_path = out_dir / f"{name}.json"
    out_path.write_text(json.dumps({
        "name": name,
        "profile": profile,
        "system_prompt": system_prompt,
        "transcript": transcript,
    }, indent=2))
    print(f"\nSaved profile to {out_path}")
    return out_path
