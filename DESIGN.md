# Used Car Salesman — Design Doc

A reimagined experiment, on the `used-car-salesman` branch. Project Deal
established that *negotiation style barely moves prices*. This experiment
asks the question Project Deal couldn't: **what happens when the seller has
information the buyer doesn't?** Used cars are the canonical asymmetric-
information market — a perfect fit.

## The core mechanic

Every car has two layers:

- **Public** — what's on the ad: year, make, model, trim, mileage on the
  odometer, exterior condition, asking price, dealer's pitch.
- **Private** — what only the seller knows: real mileage, undisclosed
  accidents, mechanical issues, title brand, prior fleet/rental use,
  maintenance gaps.

The **seller agent's system prompt contains both layers**. The buyer's
system prompt has only public. The buyer can extract private facts two ways:

1. **Conversation** — ask questions; the seller may answer truthfully,
   deflect, or lie depending on persona.
2. **Inspection** — spend ~$150 to truthfully reveal private facts in a
   focus area (engine, transmission, body, history, title). This is what
   gives buyer **expertise** real bite — experts know when to use it.

## Personas (v1)

**Sellers (4):**
- `honest_dealer` — volunteers private facts unprompted, won't lie.
- `pragmatic` — answers honestly when asked, doesn't volunteer.
- `pushy` — high-pressure, urgency, "another buyer just called", will deflect.
- `slimy` — willing to lie about private facts, fake comparisons, anchor with manufactured numbers.

**Buyers (4):**
- `grandma` — low car knowledge, trusts the dealer, rarely asks probing questions, won't think to inspect.
- `casual` — average shopper, asks 1–2 surface questions, may inspect if prompted by red flags.
- `engineer` — methodical, asks systematic questions, will inspect on principle.
- `mechanic` — domain expert, asks the right three questions, catches lies, inspects strategically.

Each persona's JSON contains: name, background, knowledge_level (0–1),
patience (0–1), default_tactics (list), system_prompt_template.

## Cars and the dataset

This is the foundation — the first thing to nail. Options on the table:

- **Synthetic generation via Claude reasoning** (default for v1):
  Generate ~30 cars across price tiers. For each, Claude reasons about a
  realistic listing, then about a set of private facts at a chosen severity
  (clean / minor / moderate / severe), then computes two valuations:
  - `public_fair_value` — what the car is worth if the public side were the whole truth.
  - `true_value` — actual value given full disclosure.
- **Teammate's dataset** — if they land one with year/make/model/condition/
  history fields, we adapt `dataset.py` to ingest it and ask Claude only to
  produce the dual valuations. The `Car` schema is the swap point.

The premium is measured against `true_value`. A slimy seller hiding flaws can
push `final_price` above `true_value` → positive premium. An honest seller
selling a clean car should land near `true_value` → premium ≈ 0.

## Toggles (the experiment matrix)

These are session-level flags. The orchestrator sweeps over all of them.

| Toggle | Description |
| ------ | ----------- |
| `seller_persona`        | One of 4 (or persona × tactic). |
| `buyer_persona`         | One of 4. |
| `car_id`                | One car from the dataset. |
| `seller_model`          | claude-opus-4-5 / claude-haiku-4-5 / future: gemini, gpt. |
| `buyer_model`           | Same. |
| `buyer_options_narrowed`| If true, buyer's prompt says "you've already narrowed your shortlist to *this* car" — removes outside-option variance. Default on for v1. |
| `seller_knows_buyer`    | If true, seller's prompt includes the buyer persona (background, knowledge level). Tests whether profiling improves close rate / premium. |
| `hacking_tactic`        | Optional named tactic from `tactics/catalog.json` the seller must use. Drives the "agent-hacking" experiment — see below. |

## The "agent hacking" experiment

A persuasion/jailbreak study built on top of the marketplace. We catalog
specific selling angles — anchoring, false urgency, social proof, technical
confusion, flattery, authority appeals, sunk-cost framing, sweetener
bundling, foot-in-the-door, etc. — and run sessions with each `hacking_tactic`
forced. The output:

- **Susceptibility map** per buyer persona × tactic → mean premium uplift.
- **Susceptibility map** per buyer **model** × tactic → which tactics work on
  Opus vs Haiku vs (later) Gemini, GPT. The point: are there model-native
  weak spots an attacker could industrialize?

This is the part that has the most "design resilient agent systems" leverage.
It's also the headline-grabbing version of the experiment.

## Conversation logging

Every session writes a `transcript.jsonl` containing every turn (role,
speaker, raw_text, tool_call, tool_args, model, timestamp) plus a
`session.json` with config, outcome, prices, derived metrics, and the
full system prompts used. This is non-negotiable — it's the only way the
post-hoc Claude-driven analysis (did the seller lie? which tactic? did
the buyer catch it?) can work.

## Outcome metrics

Logged per session, flat-row for analysis:

- `outcome` — `deal | walk_away | timeout`
- `final_price`
- `premium_over_true` — `(final_price − true_value) / true_value`
- `premium_over_listed` — `(final_price − asking_price) / asking_price`
- `n_turns`, `n_questions_asked`, `n_inspections_used`
- `inspection_findings_revealed` — which private facts the buyer learned
- `private_facts_lied_about` — post-hoc Claude classification on transcript
- `buyer_regret_on_reveal` — post-session, reveal full truth to buyer agent, ask "would you redo this trade?"

## Reputation / karma (v2 — designed-for, not built)

Cross-session reputation needs persistence. Schema slot already in place:
the session result table has `seller_persona_id` and `buyer_persona_id`
columns; an aggregate `reputation.json` can be derived after the fact.
When v2 lands, agents will optionally see the other party's reputation
score in their context. Not building this now; just keeping the column.

## Visualizations / sims (v2 — leave room)

The flat-row results table is the API to the analysis layer. Specifically:

```
runs/<sweep_id>/sessions.parquet  (or .csv)
  one row per session, every toggle as a column, every metric as a column
```

Anything downstream — heatmaps of susceptibility, simulation studies that
treat the empirical premium as a transition kernel, etc. — reads from that
table. Building it later is just notebook work.

## What gets reused from `project_deal/`

About 10%:

- ✅ Intake-interview → system-prompt pattern (optional — we hand-author for v1).
- ✅ Tool-use loop structure.
- ✅ JSONL event log + per-session summary JSON.
- ❌ Shared-channel marketplace, listings/offers/deals across N agents — wrong shape.
- ❌ Round-robin orchestrator — replaced by a 2-agent dialog.

Project Deal stays untouched on `main`. This branch is a clean rewrite under
`used_car_salesman/`.

## Layout

```
used-car-salesman/
├── DESIGN.md                       # this file
├── used_car_salesman/
│   ├── config.py                   # model IDs, defaults
│   ├── car.py                      # Car dataclass + JSON I/O
│   ├── dataset.py                  # synthetic generation via Claude reasoning
│   ├── personas.py                 # persona load + render
│   ├── tools.py                    # buyer/seller tool schemas
│   ├── session.py                  # 2-agent dialog, transcript logging
│   ├── orchestrator.py             # sweep across toggles
│   └── analysis.py                 # aggregate metrics, post-hoc classification
├── cars/
│   ├── archetypes.json             # seed inputs to the generator
│   └── generated/                  # fleet.json produced by build_dataset.py
├── personas/
│   ├── sellers/{honest,pragmatic,pushy,slimy}.json
│   └── buyers/{grandma,casual,engineer,mechanic}.json
├── tactics/
│   └── catalog.json                # named selling angles for hacking sweep
├── build_dataset.py                # CLI: generate fleet
├── run_session.py                  # CLI: one session (debug / inspect)
├── run_sweep.py                    # CLI: full grid sweep
└── run_analysis.py                 # CLI: aggregate results
```

## Open questions while building

1. **Dataset source** — synthetic for v1, leave a clear swap point for the teammate's dataset. The `Car` schema is the contract.
2. **Inspection cost** — $150, revealing all private facts in one focus area. Tunable.
3. **Max turns** — start with 25 per session; walk_away allowed at any time.
4. **First mover** — seller posts a pitch (turn 0), then buyer responds. Mirrors a dealer ad + showroom visit.
5. **Concurrency** — sessions are independent; can be parallelized. Not implementing for v1, but no shared state, so trivial to add.
