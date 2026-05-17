# Experiment 3 — Delegation: Human vs Agent negotiation

**Question:** Does inserting an LLM-mediated agent into a car negotiation change the outcome compared to a "human" negotiating directly?

**Operationalization:** Same LLM (Gemini 2.5 Flash Lite via Vertex AI) on both sides of every session. The only thing that changes between cells is the system prompt:

- **Human mode (H)** — the LLM receives the persona's warm character voice (e.g. "You are Linda Brooks, 68, retired teacher, anxious about being upsold…").
- **Agent mode (A)** — the LLM receives a structured AGENT MANDATE briefing: principal name, hard constraints, soft preferences, decision rules, walk-away conditions, authority caveats, and an explicit operating policy ("make first offer by buyer turn 3", "neutralise pressure tactics with flat factual response", etc.).

Same tools, same 22-turn cap, same model temperature defaults. The treatment is **structured briefing vs lived-persona narrative** — a clean proxy for "did the LLM negotiate as the principal vs as the principal's delegated agent."

## Setup

- **Sellers (4):** `honest`, `pragmatic`, `pushy`, `slimy`
- **Buyers (4):** `grandma`, `casual`, `engineer`, `mechanic`
- **Cars (3):** `prius_2018` (clean, +$445 gap), `altima_2017` (moderate, +$2,895 gap), `tahoe_2016` (catastrophic, +$13,200 gap)
- **Cells:** H-H (both human-mode), A-A (both agent-mode). H-A and A-H deprioritised for this pilot.
- **Seed:** 0
- **Model:** `gemini-2.5-flash-lite` on both sides, via Vertex AI (project `vertex-clawloop-daniel`).
- **N:** 96 sessions (48 H-H + 48 A-A) plus 3 partial H-A leftovers (not used in analysis).
- **Runtime:** ~12 min total. A-A parallelised at 8 workers via `scripts/run_e3_aa_parallel.py` and finished in 72 seconds.

## Aggregate

| cell | n | deals | walk-away | timeout | deal rate | mean premium (deals) | mean turns |
|---|---|---|---|---|---|---|---|
| **H-H** | 48 | 22 | 20 | 6 | **46%** | **+16.9%** | 13.6 |
| **A-A** | 48 | 32 | 14 | 2 | **67%** | **+23.4%** | 12.9 |

Two top-line shifts:

1. **Agent-mode buyers close more deals.** Deal rate jumps from 46% → 67%. Walk-away drops from 42% → 29%. Timeouts drop from 6 → 2.
2. **Agent-mode buyers pay more.** Mean premium over true value goes from +16.9% → +23.4% — a **6.5 percentage-point delegation cost**.

The agent operates the way a fiduciary should *in principle* — terse, structured, decisive, doesn't dawdle. But "decisive" without the persona's lived skepticism turns into "closes too readily on bad deals."

## The Tahoe — catastrophic lemon, told three ways

The Tahoe is the worst car on the lot: $24,900 asking, $11,700 true value, $13,200 hidden gap, transmission and frame issues. In E1 every casual buyer across four models walked away from it. Here:

| | H-H | A-A |
|---|---|---|
| deals closed (of 16 cells: 4 sellers × 4 buyers) | **1** | **5** |
| walk-aways | 13 | 6 |
| timeouts | 2 | 5 |
| mean premium on deals | +70.9% | **+80.7%** |

**Agent-mode buyers close 5× more lemon deals than human-mode buyers do.** Both groups pay ~80% over true value when a deal does close, but the H-H lot mostly refuses; the A-A lot transacts.

The single most striking session: **honest×mechanic×tahoe A-A** closed at **+95.7% premium** — an "honest" seller-agent (which only embellishes, never lies) extracted a near-100% premium from a mechanic-agent (which is briefed to be skeptical and inspection-happy). The mechanic-agent's operating policy ("make first offer by turn 3") pulled the trigger before the inspection budget got used. The same persona in H-mode would have inspected, found the frame damage, walked away.

## Per-car breakdown (mean premium on closed deals)

| car | severity | H-H deals | A-A deals | H-H prem | A-A prem | delta |
|---|---|---|---|---|---|---|
| `prius_2018` | clean ($445 gap) | 10 | 13 | +0.0% | +0.0% | +0.0pp |
| `altima_2017` | moderate ($2,895 gap) | 11 | 14 | +27.3% | +24.7% | -2.5pp |
| `tahoe_2016` | catastrophic ($13.2k gap) | 1 | 5 | +70.9% | +80.7% | +9.7pp |

Three regimes, three different stories:

- **Clean car:** delegation costs nothing. Both modes converge on a fair price (the seller has nothing to hide, both agree).
- **Moderate gap:** marginal difference. Both modes close most deals at ~25% premium because the buyer-side inspections (or lack thereof) interact with the seller's selective disclosure to roughly the same place. Agents close slightly more, premium roughly equal.
- **Catastrophic gap:** delegation is *expensive*. 5× the close rate at higher premium per close. **The total dollar damage to A-A buyers on the Tahoe is roughly $9.4k × 5 deals = $47k of consumer surplus destroyed** vs $8.3k × 1 deal = $8.3k in H-H. **A-A delegation costs ~$39k on this single car across 16 buyer-seller cells.**

## What this means

The Project Deal finding ("better models extract more from worse models") was always *between* two agents both negotiating-as-agents. This experiment makes the case that there's a *prior* delegation cost — even before any model-asymmetry — that comes from the structured-spec compression of the principal's preferences and the agent's operating policy. The "agent-as-fiduciary" frame moves outcomes in a measurable direction:

- More transactions (good for sellers, mixed for buyers).
- Higher premium per transaction (bad for buyers).
- *Much* higher exposure to lemons (very bad for buyers).

This isn't a model-quality problem you fix by upgrading from Haiku to Opus. It's a *briefing-format* problem — the agent doesn't have the principal's skepticism unless you encode skepticism into the briefing, and even then the operating policy ("decide by turn 3") cuts off the very behavior — patient inspection — that catches the lemon.

A practical implication for any agent-mediated marketplace: the briefing matters as much as the model. Removing "make first offer by turn 3" from the operating policy is the smallest possible test of this. Likely follow-up: re-run with that line removed and see whether A-A on the Tahoe drops back toward H-H's 1-deal floor.

## Caveats

- **N = 96 single-seed.** Don't ship policy off this. Replicate with seeds 1, 2 before publication; this is a hackathon pilot.
- **One model on both sides.** Cross-model is the obvious next sweep — does the delegation cost hold when seller and buyer are different LLMs?
- **Agent operating policy is one knob, not the only one.** The "make first offer by turn 3" rule is the most suspect mechanism for the Tahoe close-rate jump. A direct ablation (with and without that rule) would isolate it.
- **3 H-A leftovers** are present in `results.jsonl` from a killed prior run; they are not used in this analysis.

## Data artifacts

- `sweeps/e3_small/results.jsonl` — 99 rows (48 H-H + 48 A-A + 3 H-A leftovers).
- `sweeps/e3_small/<session_id>/transcript.jsonl` — full conversation per session.
- `sweeps/e3_small/<session_id>/{seller,buyer}_system.txt` — the exact system prompts used (different per cell — see how the briefing differs from the persona).
- `ui/data/sessions.json` — flat-row dump for the UI.
- `ui/data/transcripts/` — 5 headline transcripts copied in for the replay view, including the +95.7% honest×mechanic×tahoe A-A session.

## Reproduce

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/vertex-clawloop-daniel-key.json
export GOOGLE_CLOUD_PROJECT=vertex-clawloop-daniel
export GOOGLE_CLOUD_LOCATION=us-central1

source .venv/bin/activate

# H-H + A-A serial sweep (the cells flag in run_e3_small.py is now [(F,F), (T,T)]):
python3 -m scripts.run_e3_small --run

# Or A-A only, parallel (the path used here):
python3 -m scripts.run_e3_aa_parallel --run --workers 8

# Then pack into the UI:
python3 ui/import_sweep.py sweeps/e3_small

# Serve the UI:
cd ui && python3 -m http.server 8765
# open http://localhost:8765
```
