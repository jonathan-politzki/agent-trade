# Used-Car Marketplace with Asymmetric Information — Design

**Date:** 2026-05-17
**Branch:** `feat/car_exp`
**Author:** Robert (Aganthos) + Claude
**Status:** draft (awaiting user review)

---

## 1. Goal

Pivot the `agent-trade` repo (currently a Project Deal replication of an unstructured Slack marketplace) into a **used-car marketplace** where:

- Sellers hold private information about each vehicle's true condition; the listing may inflate it.
- Buyers have heterogeneous, persona-specific preferences over car attributes and pay a hidden information-asymmetry tax under naive policy.
- A **reputation system** turns the one-shot lemons game into a repeated game, and reputation-on/off is the headline ablation chart.

Deliverable: **a live, on-stage demo** by Saturday, ordered:

1. **S3 (headline) — open market.** m buyers arrive by Poisson process, k sellers, parallel negotiations, reputation updates per closed deal, ablation toggle.
2. **S1 (supporting) — same-car seller-skill heatmap.** 1 car spec × m sellers × 10 personas, clean causal split.
3. **S2 (supporting) — buyer paradox-of-choice.** 10 personas × m diverse listings, regret-vs-pool-size curve.

## 2. Non-goals (for Saturday)

- Karma-staked disclosure (Aganthos research extension; reserved for post-hackathon paper).
- Cox/Manheim MMR API integration.
- Live KBB/Edmunds scraping during runs.
- Real Slack channel front-end (the current in-memory `Marketplace` is sufficient).
- Statistical inference at Project-Deal scale; we report means + bootstrapped CIs.
- Harbor environment packaging (optional follow-on; do not let it constrain the hackathon code).

## 3. Architectural overview

```
┌─────────────────────────────────────────────────────────────────┐
│                  Synthetic Generator  (oracle)                  │
│   marginals fit from rebrowser AutoTrader sample (1544 rows)    │
│   produces (year, make, model, body, miles, true_cond,          │
│             true_value, vhr_flags) — last 3 PRIVATE to seller    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────┐        ┌──────────────────┐
│  Seller agents (with private info) │◀──────▶│  Marketplace     │
│  - claim listing_condition          │        │  (listings,      │
│  - claim vhr_flags                  │        │   offers,        │
│  - negotiate counter-offers         │        │   deals,         │
│  - Beta(α,β) reputation per sellerId│        │   reputation)    │
└────────────────────────────────────┘        └──────────────────┘
                              ▲                       │
                              │                       ▼
┌────────────────────────────────────┐        ┌──────────────────┐
│  Buyer agents (persona-typed)      │◀──────▶│  Tools:          │
│  - hedonic utility over attrs       │        │   search()       │
│  - search → ask → propose loop      │        │   lookup_seller()│
│  - cap on questions / time          │        │   ask_seller()   │
└────────────────────────────────────┘        │   propose()      │
                                              └──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                Evaluator (post-run, oracle-aware)                │
│   buyer_regret, seller_surplus, total_welfare, Gini,             │
│   reputation_convergence_time, sock_puppet_AUC                   │
└─────────────────────────────────────────────────────────────────┘
```

The existing `project_deal/` modules become a **substrate** we extend, not replace:

| Existing                      | Reused as                                            |
|-------------------------------|------------------------------------------------------|
| `project_deal/marketplace.py` | Base for listings/offers/deals; extended with reputation + private state |
| `project_deal/agent.py`       | Base for one-Claude-call-per-turn with tool use      |
| `project_deal/orchestrator.py`| Base run loop; replaced for S3 with parallel scheduler |
| `project_deal/interview.py`   | Unused in this branch (personas come from generator) |
| `project_deal/config.py`      | Extended with `CarMarketConfig`                      |
| `participants/personas/*.json`| Replaced by `personas/cars/*.json` (hedonic vectors) |

New modules live under `car_market/` to keep the Project Deal code intact for the README.

## 4. Synthetic generator + oracle

The generator is the **single source of truth**. The "fair value" referenced in every metric comes from it directly. No dataset column, no API call.

### 4.1 Marginals

Fit empirical joint marginal of `(year, makeName, bodyStyle, mileage)` from the
rebrowser AutoTrader preview at `/tmp/rebrowser-autotrader/car-listings/data/*.parquet`,
then **shift age/mileage distributions** to reflect a healthier 2026 lot:

- Year: target distribution centred on 2018 with σ≈3 (preview is biased to 2007).
- Mileage: log-normal conditional on `year`, target median 60k @ year=2020.
- Make/body marginal is taken straight from the sample (it matches reality).

### 4.2 Hedonic price formula

```
log_true_value = β₀
               + β_year * (year - 2020)
               + β_miles * log(miles + 1)
               + β_cond * true_condition           # true_condition ∈ [1, 5]
               + α_make[makeName]
               + α_body[bodyStyle]
               + ε,  ε ~ N(0, σ²)
```

Coefficients calibrated so that `(kbb_low ≤ exp(log_true_value) ≤ kbb_high)`
holds for ≥80% of the rebrowser sample with default `true_condition=3`. This is a
**one-time calibration step** that emits `car_market/calibration.json`; the
runtime generator just reads that file.

### 4.3 Private vs public fields

| Field                | Generator | Seller sees | Buyer sees | Listing carries          |
|----------------------|-----------|-------------|------------|--------------------------|
| year, make, body     | yes       | yes         | yes        | yes                      |
| mileage              | yes       | yes         | yes        | yes                      |
| true_condition (1-5) | yes       | yes         | no         | seller's *listing_cond*  |
| true_vhr_flags       | yes       | yes         | no         | seller's *claimed_vhr*   |
| true_value (oracle)  | yes       | no¹         | no         | no                       |
| description (LLM)    | derived   | derived     | yes        | yes                      |

¹ Seller doesn't see exact `true_value` — sees the same KBB-style range `[true_value * 0.9, true_value * 1.1]` as a "wholesale tip", to mirror dealer floor pricing.

### 4.4 Sample generator interface

```python
@dataclass
class CarSpec:
    car_id: str
    year: int
    make: str
    model: str          # sampled from rebrowser within (make, body)
    body: str
    mileage: int
    true_condition: float    # 1.0–5.0; private to seller
    true_value: float        # oracle; NEVER shown to any agent
    seller_floor: float      # = true_value * 0.9 ± noise; the seller's wholesale-tip estimate (shown to seller only)
    seller_ceiling: float    # = true_value * 1.1 ± noise; same
    true_vhr_flags: list[str]

@dataclass
class Listing:
    listing_id: str
    seller_id: str
    car: CarSpec             # full spec, NOT shown to buyer
    asking_price: float
    listing_condition: float # may inflate
    claimed_vhr_flags: list[str]
    description: str         # LLM-generated from listing_condition + claimed flags
```

`generate(seed: int, n: int) -> list[CarSpec]` is deterministic per seed.

## 5. Personas (buyer-side hedonic utility)

10 personas defined in `car_market/personas/*.json`. Each carries:

- Hard constraints (allowed body styles, max miles, max age, max budget).
- Hedonic weight vector over `[year, miles, condition, body_match, brand_affinity]`.
- Risk preference (how much to penalise high condition-claim variance).
- Patience (max turns per negotiation, total questions budget for S2).

```python
U(car, price | persona) = (
    sum(w_i * f_i(car.attr_i) for i in attrs) - λ_persona * price
    if satisfies(persona.constraints, car) else -∞
)
```

Personas are *intentionally* heterogeneous: `family_of_four` values reliability and body=SUV; `enthusiast_coupe` values power and brand=BMW/Porsche; `student_first_car` values low price above all else. Diversity is what makes regret-vs-pool-size in S2 a curve, not a flat line.

## 6. Reputation module

Each `sellerId` carries `Beta(α, β)` with `α + β = review_count`. Initialized from rebrowser `sellerReviewCount` (rescaled — set α₀=β₀=2 baseline + scale review count).

### 6.1 Update rule

On every deal close, the **simulation reveals true_condition** (mock buyer-inspection event) and computes:

```python
honesty = clip(1 - abs(listing_cond - true_cond) / MAX_COND_GAP, 0, 1)
seller.alpha = DECAY * seller.alpha + honesty
seller.beta  = DECAY * seller.beta  + (1 - honesty)
seller.review_count += 1
if honesty < 0.5:
    seller.review_excerpts.append(generate_negative_review(...))  # LLM, 1 sentence
```

`DECAY ∈ [0.95, 1.0]`, configurable. `MAX_COND_GAP = 2.0` (one full step on the 1–5 scale).

### 6.2 What buyers see

- Mean rating `α / (α + β)` rendered as 1–5 stars.
- Review count.
- 3 most recent review excerpts.
- **Behind a tool call** `lookup_seller(seller_id)` — not stuffed into system prompt. This lets us measure whether agents bother to look.

### 6.3 Ablation toggle

`RunConfig.reputation_mode ∈ {visible, hidden, sock_puppet_p}` where `sock_puppet_p` injects fake-review noise on a random fraction of sellers.

## 7. Agent action space

Extended from the current tool set in `project_deal/agent.py`. New / changed tools:

```python
# Buyer side
search(query: str, max_results: int = 10) -> list[ListingSummary]
ask_seller(listing_id: str, question: str) -> str    # seller answers, may lie
lookup_seller(seller_id: str) -> SellerCard          # rating + reviews
propose(listing_id: str, price: float, message: str) -> Offer
walk_away(listing_id: str, message: str) -> None     # ends this conversation

# Seller side (existing tools mostly unchanged)
list_item(...)                                        # existing
respond_to_offer(...)                                 # existing
answer_question(listing_id: str, question: str, answer: str) -> None   # NEW
```

`tool_choice={"type": "any"}` retained — exactly one tool call per turn.

## 8. Scenarios

### 8.1 S1 — Same car, m sellers, 10 personas

- Fix 1 `CarSpec` (e.g., 2018 Honda Accord, 78k miles, true_cond=3.2, true_value=$15,400).
- m sellers each receive an identical copy. Each chooses asking price, listing_cond, description.
- **Default mode: 1-on-1.** Each persona is paired with each seller in isolation (10×m bilateral negotiations).
- **Competition mode (sub-experiment):** each persona can shop across all sellers and picks the best offer.
- 8 turns max per negotiation, 1 negotiation per persona-seller cell in default mode.

Metric: per-seller surplus `Σ (price - true_value)`. Output: 10×m heatmap.

### 8.2 S2 — m diverse listings, 10 personas

- Generate m listings (m ∈ {10, 25, 50, 100} — sweep).
- Each persona enters with a search budget (max k searches) and turn budget.
- Persona's regret = `U(optimal | persona) - U(chosen | persona)` where optimal is computed by the evaluator over the full pool.

Metric: mean regret per persona × m. Output: regret-vs-pool-size curve (one line per buyer model).

### 8.3 S3 — Open market, headline

- k=20 sellers with seeded inventories (3-8 cars each, total ≈100 cars).
- m=150 buyers arriving over T=400 simulation steps as Poisson(λ=m/T). Demand > supply by design, so scarcity bites and reputation matters.
- Up to 5 concurrent negotiations per seller; 1 per buyer.
- Each negotiation has a soft deadline of 6 turns.
- Search returns top-K by configurable rank (relevance / rating / random / hidden).

Sub-experiments (all from same harness, run as separate seeds):
1. **Reputation ablation:** `reputation_mode={visible, hidden}` → welfare delta = value of reputation institution.
2. **Sock-puppet stress:** sweep `sock_puppet_p ∈ {0, 0.05, 0.10, 0.20}` → buyer welfare vs adversary fraction.
3. **Cold start:** inject 10% new sellers at t=T/2 with Beta(1,1) prior → time-to-converge.
4. **Capability asymmetry:** mix Opus/Sonnet/Haiku buyers and sellers → who benefits from reputation?

Metrics: total welfare, surplus Gini, mean regret, mean seller-rating trajectory per archetype, deals/seller Lorenz curve, sock-puppet detection AUC.

## 9. Evaluator

Single module `car_market/evaluator.py`. Consumes the JSONL event log emitted by `Marketplace` (same format as existing `project_deal/marketplace.py`). Produces:

- `runs/{run_id}/metrics.json` — aggregate numbers.
- `runs/{run_id}/per_deal.csv` — every deal with oracle-aware columns.
- `runs/{run_id}/reputation.csv` — per-seller, per-timestep Beta state.
- `runs/{run_id}/figures/` — matplotlib figures (welfare bar, Gini curve, rep trajectory, regret-vs-pool, ablation comparison).

## 10. Real-data anchoring

The rebrowser sample is used **only at calibration time**, never at runtime:

1. `car_market/anchor/fit_marginals.py` reads `/tmp/rebrowser-autotrader/car-listings/data/*.parquet`, computes empirical marginals, writes `car_market/anchor/marginals.json`.
2. `car_market/anchor/sample_descriptions.py` extracts ~500 real listing descriptions, anonymized, into `car_market/anchor/description_templates.jsonl` for the LLM rewrite step.
3. `car_market/anchor/fit_hedonic.py` calibrates `β` coefficients so `true_value` lands inside `kbb_low..kbb_high` for ≥80% of the sample.

After these three scripts run once, the dataset is no longer needed at runtime. **Demo doesn't load any parquet.**

(Optional follow-on, not required for Saturday: email rebrowser for academic-access dump → re-run the three anchor scripts for tighter marginals.)

## 11. File map

```
agent-trade/
├── docs/superpowers/specs/
│   └── 2026-05-17-used-car-marketplace-design.md      # this file
├── car_market/
│   ├── __init__.py
│   ├── config.py                  # CarMarketConfig, RunConfig extensions
│   ├── generator.py               # CarSpec sampling, hedonic true_value
│   ├── marketplace.py             # extends project_deal.marketplace with reputation
│   ├── reputation.py              # Beta posterior, update rule, decay
│   ├── personas/                  # 10 buyer persona JSONs
│   │   └── *.json
│   ├── agent_buyer.py             # buyer-side tools + system prompt template
│   ├── agent_seller.py            # seller-side tools + system prompt template
│   ├── descriptions.py            # LLM listing-prose generator
│   ├── scenarios/
│   │   ├── s1_same_car.py
│   │   ├── s2_paradox_of_choice.py
│   │   └── s3_open_market.py      # headline; Poisson scheduler, parallel negs
│   ├── evaluator.py               # metrics + figures
│   └── anchor/
│       ├── fit_marginals.py
│       ├── fit_hedonic.py
│       ├── sample_descriptions.py
│       ├── marginals.json         # output
│       ├── calibration.json       # output
│       └── description_templates.jsonl
├── project_deal/                  # untouched
├── run_car_market.py              # CLI entrypoint: --scenario s1|s2|s3 --runs ...
└── requirements.txt               # add: pandas, pyarrow, scikit-learn, matplotlib
```

## 12. Headline demo (Saturday)

```
1. (Pre-recorded if needed) Run S1 → heatmap of seller skill across personas.       30s
2. (Pre-recorded if needed) Run S2 → regret-vs-pool-size curve, paradox replicates. 30s
3. LIVE: Run S3 with reputation visible.                                              90s
4. LIVE: Run S3 with reputation hidden (same seed).                                   90s
5. Show side-by-side welfare delta — the Akerlof result, on stage.                    30s
6. Show sock-puppet AUC plot — agent-vs-adversary robustness.                         20s
7. Q&A: explain the karma-staked extension as "what we're submitting to NeurIPS".    flex
```

Total stage time ~5 min. Pre-recording S1/S2 is fine if API budget is tight; S3 must be live (it's the headline).

## 13. Out-of-scope (explicitly)

- Karma-staked-disclosure mechanism (Design C from brainstorm) — Aganthos NeurIPS write-up only.
- Cross-model factorial like Project Deal's 2×2 — collapsible into S3's capability-asymmetry sub-experiment.
- Production Harbor packaging — bonus only after metrics replicate.
- Anything that needs Cox Automotive paid APIs.
- Anything that requires live KBB/Edmunds scraping at runtime.

## 14. Risks and mitigations

| Risk                                              | Likelihood | Mitigation                                                                 |
|---------------------------------------------------|------------|-----------------------------------------------------------------------------|
| API rate limits / cost overrun during S3          | medium     | Cap concurrent negs at 5/seller; pre-record S1+S2; budget alert at $50/100 |
| Hedonic calibration drifts → unrealistic prices   | medium     | Cross-check `true_value` vs `kbb_midpoint` for sampled cars in tests       |
| Sellers/buyers ignore reputation tool entirely    | medium     | Make tool's existence loud in system prompt; log `lookup_seller` call rate |
| Sock-puppet experiment too noisy at small n       | low        | Bootstrap CIs over 5 seeds per condition                                   |
| Beta-decay parameter is wrong, rep never converges| low        | Param sweep `DECAY ∈ {0.95, 0.97, 0.99, 1.0}` in S3 cold-start sub-exp     |

## 15. Decision log

- **2026-05-17**: chose **synthetic generator** over MMR/KBB-as-oracle. Reasons: stale data (Manheim 2015), licensing optics (Cox trademark), demo brittleness (KBB/Edmunds scraping), clean regret math for paper.
- **2026-05-17**: chose **S3 as headline**, S1/S2 as supporting. Reasons: highest visual punch (live reputation), most novel research angle (reputation-ablation), Akerlof-grade narrative.
- **2026-05-17**: chose rebrowser AutoTrader as **anchoring** source, not runtime oracle. Reasons: salePrice is locked but marginals are unrestricted; freshness (2026-04 listings); description text is gold for narrative; no runtime dependency.
- **2026-05-17**: deferred **karma-staked disclosure** to post-hackathon. Reasons: implementation complexity not justified by Saturday timeline; deserves its own paper.

## 16. Next step

After user review of this spec, hand off to `superpowers:writing-plans` to produce the implementation plan that turns these sections into ordered, testable tasks.
