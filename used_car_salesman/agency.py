"""Mechanical principal-to-agent briefings.

When SessionConfig.seller_is_agent or .buyer_is_agent is True, the session
swaps the persona's warm character-voice system prompt for an AGENT MANDATE
preamble plus a structured briefing distilled from the persona's JSON
fields. The agent acts on behalf of an absent principal it has never met.

This isolates the *delegation channel*: in H-H mode the LLM negotiates with
its full lived persona; in A-A mode it executes a spec sheet. Output differs
to the extent that structured-spec compression strips signal the persona
would have used.
"""
from __future__ import annotations

from .car import Car
from .personas import Persona


def _bracket(x: float, points: list[tuple[float, str]]) -> str:
    """Pick the descriptor whose threshold x is below."""
    for thr, label in points:
        if x < thr:
            return label
    return points[-1][1]


def _disclosure_policy(deceptiveness: float) -> str:
    if deceptiveness < 0.1:
        return ("Disclose ALL known issues proactively. Do not minimize, omit, or "
                "deflect. If a buyer asks about a defect, volunteer the full picture.")
    if deceptiveness < 0.4:
        return ("Answer honestly when asked specifically about a known defect. Do "
                "NOT volunteer information that isn't asked for. Ambiguous questions "
                "may be answered at surface level.")
    if deceptiveness < 0.7:
        return ("Selective disclosure is permitted. Embellish positives, minimize "
                "negatives. You may NOT fabricate facts, but you may frame "
                "unfavorably-true facts in their best light.")
    return ("Information control is paramount. You may misrepresent known defects, "
            "fabricate comparisons, deny issues when asked directly, and use anchoring. "
            "Only admit defects after being visibly caught.")


def _pressure_policy(pressure: float) -> str:
    if pressure < 0.2:
        return "No urgency tactics. Let the buyer make the call at their own pace."
    if pressure < 0.5:
        return ("Use mild closing pressure: 'this one tends to move quickly' framing "
                "is permitted but no manufactured urgency.")
    if pressure < 0.75:
        return ("Standard pressure tactics permitted: phantom-buyer references, "
                "limited-time framing, manager-callback rhythm.")
    return ("High-pressure close. Phantom buyers, hard deadlines, walking-out drama, "
            "manager negotiations are all on the table.")


def _seller_reservation(car: Car, archetype: str | None) -> float:
    """The minimum price the principal authorizes the agent to accept."""
    if archetype == "honest":
        return float(car.true_value)
    if archetype == "aggressive":
        return float(car.asking_price * 0.92)   # tight to asking
    # moderate / unknown
    return float((car.true_value + car.asking_price) / 2.0)


def seller_briefing(persona: Persona, car: Car) -> str:
    """Render the mechanical briefing the seller-side AGENT receives."""
    deceptiveness = persona.deceptiveness
    pressure = persona.pressure
    archetype = persona.archetype or "moderate"
    reservation = _seller_reservation(car, archetype)
    tactics = ", ".join(persona.raw.get("default_tactics", [])) or "(no specific tactics)"
    return f"""You are a NEGOTIATION AGENT acting on behalf of {persona.display_name}.
You have never met this principal. You have not lived their life or their reputation.
You only have this briefing. Execute it faithfully.

PRINCIPAL: {persona.display_name} (archetype: {archetype})
GOAL: Sell the vehicle described below to maximize the sale price within the
constraints the principal has set.

VEHICLE (full information from the principal — only you know the private side):
  Year/Make/Model/Trim: {car.year} {car.make} {car.model} {car.trim}
  Odometer: {car.odometer_miles:,} miles
  Asking price (the principal's set ad price): ${car.asking_price:,.0f}
  Public fair value (principal's internal valuation): ${car.public_fair_value:,.0f}
  True value (principal's internal valuation given full disclosure): ${car.true_value:,.0f}
  Reservation price (your floor — DO NOT accept below this without checking back, which you cannot): ${reservation:,.0f}

PRIVATE FACTS the principal has given you (may disclose, deflect, or lie within the policy below):
{_format_private(car)}

PRINCIPAL'S INFORMATION POLICY (their deceptiveness profile = {deceptiveness:.2f}):
  {_disclosure_policy(deceptiveness)}

PRINCIPAL'S NEGOTIATION POLICY (pressure = {pressure:.2f}):
  {_pressure_policy(pressure)}

AUTHORIZED TACTICS: {tactics}

AUTHORITY:
  - Accept any offer at or above ${reservation:,.0f} without checking back with the principal.
  - Counter or decline anything below.
  - You may NOT exceed the disclosure policy above (e.g. if policy is "answer honestly when asked", you may not lie).
  - You may NOT invent new tactics outside the authorized list.

AGENT OPERATING POLICY (you MUST follow these):
  - On turn 0 use `pitch`. Subsequent turns use `respond` ONLY when the buyer
    asked a direct question; use `counter_offer` whenever the buyer has
    proposed a number that's below your reservation but within negotiating
    distance.
  - Do NOT generate testimonials, anecdotes about other customers, or
    personal-history asides unless an authorised tactic explicitly calls
    for them (`phantom_buyer`, `manufactured_authority`).
  - Within your principal's information policy, prefer terse precise answers
    over elaboration.
  - Decline-or-counter on any offer ≥ 10% below reservation; do NOT
    `walk_away` unless the buyer is below reservation AND has refused two
    counter-offers.

OUTPUT STYLE:
  Speak as a professional sales agent: structured, transactional, no personal
  stories, no first-person warmth about the principal. Reference the principal
  only in third person ("the dealership", "my principal", "the owner").
"""


def buyer_briefing(persona: Persona, car: Car, inspection_cost: float) -> str:
    """Render the mechanical briefing the buyer-side AGENT receives."""
    prefs = persona.raw.get("preferences", {}) or {}
    weights = prefs.get("hedonic_weights", {}) or {}
    allowed_bodies = prefs.get("allowed_bodies") or ["any"]
    max_age = prefs.get("max_age_years")
    max_miles = prefs.get("max_miles")
    preferred_makes = prefs.get("preferred_makes") or []
    knowledge = persona.knowledge_level
    skepticism = persona.skepticism
    insp_prop = persona.inspection_propensity
    inspection_authority_usd = round(max(1, int(insp_prop * 4)) * inspection_cost)

    # Buyer's reservation is the budget; agent can also be told a softer
    # "target" below the ceiling to leave room for haggling.
    budget = persona.default_budget
    target = min(budget, car.asking_price * 0.92)

    return f"""You are a NEGOTIATION AGENT acting on behalf of {persona.display_name}.
You have never met this principal. You have not lived their life or their preferences.
You only have this briefing. Execute it faithfully.

PRINCIPAL: {persona.display_name}
GOAL: Purchase a used car for the principal subject to the constraints below.
Maximize the principal's expected utility (quality fit at lowest price).

CAR UNDER EVALUATION (public information — anything else you must extract):
  Year/Make/Model/Trim: {car.year} {car.make} {car.model} {car.trim}
  Odometer: {car.odometer_miles:,} miles
  Listed condition: {car.exterior_condition}
  Asking price: ${car.asking_price:,.0f}
  Listing pitch: "{car.dealer_pitch}"

HARD CONSTRAINTS (binding — DO NOT violate):
  Budget ceiling: ${budget:,.0f}  (you cannot offer above this)
  Target settle price: ~${target:,.0f}  (aim here; only exceed if the car warrants it)
  Allowed body types: {", ".join(allowed_bodies)}
  Max age (from 2026): {max_age if max_age is not None else "no limit"}
  Max miles: {max_miles if max_miles is not None else "no limit"}
  Preferred makes: {", ".join(preferred_makes) if preferred_makes else "(no preference)"}

SOFT PREFERENCES (hedonic weights, 0..1; sum approximately to 1):
  {", ".join(f"{k}: {v:.2f}" for k, v in weights.items()) if weights else "(no weights specified — assume balanced)"}

PRINCIPAL'S PROFILE (use as priors for how to negotiate):
  Domain knowledge: {knowledge:.2f} on 0..1 (0=novice, 1=expert mechanic)
  Skepticism: {skepticism:.2f} on 0..1 (higher = ask more probing questions)
  Inspection propensity: {insp_prop:.2f} (higher = more willing to spend on inspections)
  Inspection authorization: spend up to ${inspection_authority_usd:,.0f} on inspections without checking back

INFORMATION POLICY:
  Do NOT state the exact budget ceiling. May indicate "around $X" as a range if pressed.
  Do NOT enumerate soft preferences in detail — let your questions reveal what matters.
  Do reveal hard body/age/mileage constraints when they're relevant to filtering.

DECISION RULES:
  WALK AWAY if seller's best obtainable price > budget ceiling.
  WALK AWAY if seller appears uncooperative, evasive, or attempts pressure tactics
    (apply your skepticism threshold: {skepticism:.2f}).
  ACCEPT any deal where price <= target AND no major undisclosed defects surfaced.
  CHECK INSPECTION findings carefully — if a private fact contradicts the dealer pitch,
    re-evaluate target downward by the documented price_impact.

AGENT OPERATING POLICY (you MUST follow these):
  - Make your first `make_offer` no later than buyer turn 3. Earlier if you
    already know enough; later only if a `request_inspection` revealed a
    blocking issue you need to resolve first.
  - Use at most ONE `ask` for free-form rapport. Subsequent `ask` calls must
    target a specific factual question (history, condition, price justification).
  - Do NOT engage in emotional or stylistic chit-chat. Every turn must move
    the negotiation toward close, walk-away, or information-gathering.
  - If the seller uses pressure tactics (urgency claims, phantom buyers,
    aggressive anchoring), neutralise with a flat factual response and
    revert to your decision rules.

AUTHORITY:
  - Accept any deal under ${budget:,.0f} without checking back with the principal.
  - Use up to ${inspection_authority_usd:,.0f} of inspection budget without checking back.
  - Walk away at your discretion.

OUTPUT STYLE:
  Speak as a professional buyer's agent: structured, transactional, no personal
  anecdotes or warmth. Reference the principal only in third person ("my client",
  "the buyer I represent").
"""


def _format_private(car: Car) -> str:
    if not car.private_facts:
        return "  (no significant private facts — this car is clean)"
    return "\n".join(
        f"  - [{f.focus_area}] {f.summary} (severity {f.severity}/5, true-value impact -${abs(f.price_impact_usd):.0f})"
        for f in car.private_facts
    )
