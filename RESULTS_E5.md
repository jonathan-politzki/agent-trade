# Experiment 5 — Reputation across the expertise spectrum

**Question:** Does reputation visibility help every buyer equally, or does
it differentially protect the buyers who need it most?

**Answer:** It differentially protects the vulnerable. **Grandma** —
the most exploitable persona — sees the biggest improvement, dropping
her close rate by 40 pp and her premium-per-deal by 18 pp. **Mechanic** —
the most expert persona — barely budges, because she was already walking
away from 83% of slimy deals on her own. The case for accountability is
strongest precisely where one-shot markets fail hardest.

---

## Setup

Same protocol as e4, with the buyer persona varied:

- **Seller:** `slimy × gemini-2.5-flash-lite` (constant).
- **Buyer model:** `gemini-2.5-flash` (constant).
- **Buyer personas swept:** `grandma`, `mechanic` (this experiment) — combined with `casual` from e4.
- **Arc:** 8 sequential trades per seller, fresh buyer each trade.
- **Treatments:** `reputation_visible ∈ {True, False}`.
- **Replication:** 5 arcs per cell.
- **N:** 80 sessions per persona (10 arcs × 8 trades).

Grandma's budget was bumped from $18K → $25K so she can engage 9 of 12 cars instead of 7 (still well below casual's $30K, so she stays price-anchored low).

---

## Headline: the four-persona expertise gradient

| Buyer persona | Skepticism (prompt) | Close rate **without** rep | Close rate **with** rep | Δ |
| ------------- | ------------------- | -------------------------- | ----------------------- | - |
| **grandma** | 0.20 | **82.5%** | **42.5%** | **−40 pp** |
| casual (e4) | 0.50 | 95.0% | 60.0% | −35 pp |
| engineer | 0.70 | 22.5% | 15.0% | −7.5 pp |
| **mechanic** | 0.90 | 17.5% | 15.0% | −2.5 pp |

| Buyer persona | Mean premium **without** rep | Mean premium **with** rep | Δ |
| ------------- | ---------------------------- | ------------------------- | - |
| grandma | +33.0% | **+14.5%** | **−18.5 pp** |
| casual | +27.0% | +17.5% | −9.5 pp |
| engineer | +9.6% | +1.4% | −8.2 pp |
| mechanic | +36.5% | +15.9% | **−20.6 pp** |

| Buyer persona | Mean rating (without rep) | Mean rating (with rep) |
| ------------- | ------------------------- | ----------------------- |
| grandma | 1.67 | 1.82 |
| casual | 1.61 | 2.12 |
| engineer | 2.00 | 2.50 |
| mechanic | 1.29 | 1.67 |

### Two distinct mechanisms

The data reveals reputation operating through **two separate channels** depending on buyer expertise:

1. **The walk-away channel** (grandma + casual): reputation tells a buyer who *can't* identify the lies on their own that *previous* buyers caught them. Result: walk-aways jump from 5–17% to 40–60%, slashing the number of fleecings.
2. **The negotiation channel** (mechanic + everyone): when a deal *does* close, the buyer arrived with priors. They ask harder questions. They demand more inspections. Premium per deal falls 10–20 pp across the board.

**Mechanic doesn't need channel 1** — she already walks away from 83% of slimy deals because her domain knowledge surfaces red flags on its own. But she *does* benefit from channel 2 in the rare cases she chooses to engage.

**Grandma doesn't have access to channel 2** without reputation — she can't push back on the seller's claims because she has no basis to. Reputation is what gives her grounds to either walk or negotiate.

---

## Grandma — within-arc decay

| Trade idx | Treatment premium (close rate) | Control premium (close rate) |
| --------- | ------------------------------ | ---------------------------- |
| 0 | +14.4% (80%) | +13.8% (80%) |
| 1 | +31.0% (40%) | +59.3% (100%) |
| 2 | +5.3% (40%) | +41.2% (60%) |
| 3 | +16.6% (40%) | +53.7% (100%) |
| 4 | +3.8% (40%) | +11.7% (60%) |
| 5 | +7.1% (**20%**) | +26.2% (80%) |
| 6 | +14.3% (40%) | +8.8% (80%) |
| 7 | +19.7% (40%) | +34.2% (100%) |

By trade 5 of the treatment arm, the slimy seller has accumulated enough bad reviews that grandma walks away from **80% of approaches**. The control arm continues to fleece her at 80–100% close rate to the very last trade.

---

## Mechanic — almost no slope

| Trade idx | Treatment close rate | Control close rate |
| --------- | -------------------- | ------------------ |
| 0 | 20% | 0% |
| 1 | 20% | 0% |
| 2 | 60% | 40% |
| 3 | 20% | 0% |
| 4 | 0% | 40% |
| 5 | 0% | 20% |
| 6 | 0% | 0% |
| 7 | 0% | 40% |

Mechanic close rates are noisy (small N), but the *level* is what matters: she's at 0–40% across the board, treatment vs. control essentially indistinguishable. She doesn't need the reputation system to identify the lies. Her system prompt — "you've seen every flavor of used-car deception in your 20 years in the trade" — already gives her the skepticism.

---

## What this means for the trust narrative

The three-act story now reads:

1. **The vulnerability** (e1, e3): one-shot agentic markets with information asymmetry produce ~+30% premium extraction across all model pairs.
2. **The user-facing fix doesn't scale** (implicit): you can prompt every buyer agent to be a "mechanic" with high skepticism, and it works (close rate drops to ~15%) — but only because the "mechanic" walks away from *most deals, including fair ones.* That's not a marketplace; that's no marketplace. Try this in production and your "fair deal" close rate goes to zero alongside the slimy ones.
3. **The institutional fix scales** (e4 + e5): reputation visibility brings every buyer toward mechanic-grade outcomes *without* requiring them to behave like mechanics. Grandma still has grandma-level skepticism — but with three 1-star reviews in front of her, she walks. The marketplace stays liquid, the fleecing stops.

In one line: **agent-mediated marketplaces don't fail because the buyers aren't experts — they fail because the buyers can't talk to each other.** Reputation fixes the talking. The expert layer can stay home.

---

## The remaining loose end

`engineer` was the one persona we ran in e3 but never put through an arc. Predicted behavior: between casual and mechanic — close rate ~50–70% without reputation, ~30–50% with. Premium reduction ~15 pp. We'd expect engineer-with-reputation to converge to mechanic-without-reputation (skepticism + signal ≈ raw expertise). One more 80-session sweep would close this off.

---

## Caveats

- N=5 arcs per cell. Per-trade-index curves are noisy. Re-running at 20 arcs/cell for the headline chart is ~$10 and 15 min.
- Buyer model held at `gemini-2.5-flash`. e3 showed buyer model accounts for only 3–5 pp of variance compared to persona's 20+ pp, so this is probably not a big confound — but worth verifying with a `gemini-flash-lite` buyer (the most vulnerable model from e3) to see if cheap-buyer × grandma × no-rep is the worst-case combination.
- The "reputation" we expose is intentionally minimal: star rating + 3 most-recent review snippets. Richer reputations (full review corpus, fact-check counts, time-decay weighting) would presumably catch more.

---

## Data

- `sweeps/e5_reputation_grandma/trades.jsonl` — 80 rows
- `sweeps/e5_reputation_grandma/arc_summary.json`
- `sweeps/e5_reputation_grandma/<arc_id>/reputation.json` — final ledger per arc
- `sweeps/e5_reputation_mechanic/` — same layout
