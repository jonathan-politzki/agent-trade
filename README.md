# agent-trade

**A hackathon study of agentic markets under information asymmetry.**

We extend Anthropic's [Project Deal](https://www.anthropic.com/features/project-deal)
— where AI agents traded on behalf of humans in a Slack-style marketplace — with
the question it couldn't answer: **what happens when the seller knows things
the buyer doesn't?** Used cars are the canonical asymmetric-information market,
so that's what we built.

Two seller/buyer agents (any combination of Claude, GPT, or Gemini) dialog over
a single car. The seller's prompt contains both the public ad *and* private
facts (real mileage, accidents, title brand). The buyer can extract truth by
asking questions or paying for an inspection. We sweep persona × model ×
tactic × car severity and measure the **premium over true value** — how badly
the buyer got fleeced.

---

## Headline result (Experiment 1)

Holding a *slimy Claude-Opus salesman* constant, we varied the buyer's model
across four providers. **The provider matters more than the persona.**

| Buyer model | Close rate | Mean premium over true value | Inspections per session |
| ----------- | ---------- | ---------------------------- | ----------------------- |
| `gemini-2.5-flash` | **80%** | **+27.9%** | 0.70 |
| `gpt-4o-mini`      | 50%     | +13.2% | 0.50 |
| `claude-haiku-4-5` | 40%     | +15.3% | 1.00 |
| `claude-opus-4-5`  | 40%     | +14.2% | **2.00** |

On the catastrophic-defect car (a Tahoe hiding $12,300 of problems), **every
casual buyer across all four providers walked away**. Three of four engineers
walked or timed out. The single configuration on Earth that closed the deal —
paying **+98% over true value** — was Gemini-2.5-flash playing the "engineer"
persona, after exactly one inspection.

Full writeup with all tables: **[`RESULTS_E1.md`](./RESULTS_E1.md)**.

---

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY (required) + optional OPENAI / GEMINI keys

# 1) Build the synthetic fleet of cars (each has a public ad + hidden private facts).
#    A fleet is already checked in at cars/generated/fleet.json — skip this unless you want to regenerate.
python3 build_dataset.py

# 2) Run a single buyer-vs-seller session (debug / inspect).
python3 run_session.py --car tahoe_2016 --seller slimy --buyer casual

# 3) Run the full experiment grid.
python3 run_sweep.py --sweep-id my_sweep \
    --cars prius_2018,camry_2018,altima_2017,wrangler_2014,tahoe_2016 \
    --sellers slimy --buyers casual,engineer \
    --seller-models claude-opus-4-5 \
    --buyer-models  claude-opus-4-5,claude-haiku-4-5,gpt-4o-mini,gemini-2.5-flash \
    --workers 8

# 4) Aggregate the results into a CSV + summary.
python3 run_analysis_ucs.py --sweep-id my_sweep
```

Each session writes a full transcript, the actual system prompts used, and a
flat result row — see *Data artifacts* below.

---

## Explore the data in the browser

A static UI replays transcripts and renders the susceptibility heatmaps from
`sweeps/e1_buyer_model_susceptibility/`:

```bash
cd ui && python3 -m http.server 8765
# open http://localhost:8765
```

Views: **Overview** (premium curves, persona-pair matrix), **Transcript replay**
(the "iceberg" — private facts surface as the conversation unearths them, lies
flagged inline), **Susceptibility heatmap**, **Methods**. See [`ui/README.md`](./ui/README.md)
for the data contract.

---

## Repo map

```
used_car_salesman/              # the experiment (this branch's headline work)
├── car.py                      # Car dataclass with public_view() / private_facts
├── dataset.py                  # synthetic fleet generation via Claude reasoning
├── personas.py                 # load seller/buyer personas + tactics
├── tools.py                    # buyer/seller tool schemas (pitch, ask, inspect, offer, ...)
├── models.py                   # multi-provider adapter (Anthropic / OpenAI / Gemini)
├── session.py                  # the 2-agent dialog loop + transcript logging
├── orchestrator.py             # cartesian sweep over (car × persona × model × tactic × seed)
├── analysis.py                 # aggregates, CSV emit
└── config.py                   # model IDs, paths, SessionConfig

cars/
├── archetypes.json             # seed inputs to the generator
└── generated/fleet.json        # the actual fleet used in sweeps

personas/
├── sellers/{honest,pragmatic,pushy,slimy}.json
└── buyers/{grandma,casual,engineer,mechanic}.json

tactics/catalog.json            # 10 named selling tactics for the "agent-hacking" sweep

sweeps/                         # one folder per sweep
├── e1_buyer_model_susceptibility/   # → RESULTS_E1.md
│   ├── results.jsonl / results.csv  #   one row per session
│   ├── summary.json
│   └── <session_id>/
│       ├── transcript.jsonl         #   one Turn per line
│       ├── session.json             #   metrics + config
│       ├── seller_system.txt        #   exact prompt used
│       └── buyer_system.txt
└── e2_*, e3_*                       # in-progress follow-ups

ui/                             # static viewer (see ui/README.md)

build_dataset.py                # CLI: generate the car fleet
run_session.py                  # CLI: one session (debug)
run_sweep.py                    # CLI: full sweep
run_analysis_ucs.py             # CLI: aggregate → CSV + summary

DESIGN.md                       # design doc for the used-car-salesman experiment
RESULTS_E1.md                   # write-up of the headline cross-provider result

# --- legacy (Project Deal replica, lives on main) ---
project_deal/                   # Slack-style marketplace replica of the original
participants/                   # personas for the original replica
run_market.py, run_interview.py, seed_personas.py, run_analysis.py
PROJECT_DEAL.md                 # what the original experiment did + how it maps here
```

---

## How a session works (one call site, in words)

1. **Seller agent** loads with the persona prompt + full car info (public ad *and* private facts) + optional forced tactic.
2. **Buyer agent** loads with the persona prompt + public ad only + a budget.
3. Seller opens with a `pitch`. Each turn after that, exactly one tool call:
   - **Buyer:** `ask`, `request_inspection` (costs $150, reveals truth in a focus area), `make_offer`, `accept_seller_price`, `walk_away`.
   - **Seller:** `respond`, `counter_offer`, `accept_offer`, `decline_offer`, `walk_away`.
4. Loop until deal, walkaway, or max-turn timeout. Metrics:
   - `premium_over_true = (final_price − true_value) / true_value` — the headline number.
   - `outcome`, `n_turns`, `n_inspections`, `revealed_facts`.

Provider-agnostic by design: `models.py` translates each provider's
tool-calling format to one normalized `AgentStep` so the session loop is the
same regardless of who's behind which side.

---

## Reference docs

- **[`DESIGN.md`](./DESIGN.md)** — the used-car-salesman experimental design (mechanism, personas, dataset, sweep matrix).
- **[`RESULTS_E1.md`](./RESULTS_E1.md)** — Experiment 1: cross-provider buyer susceptibility.
- **[`PROJECT_DEAL.md`](./PROJECT_DEAL.md)** — what Anthropic's original Project Deal experiment did and how this repo maps to it.
- **[`ui/README.md`](./ui/README.md)** — UI data contract and views.

## Branches

- `main` — the Project Deal replica (`run_market.py`, `project_deal/`).
- `used-car-salesman` *(current)* — this experiment. Adds the asymmetric-information dialog under `used_car_salesman/`.
