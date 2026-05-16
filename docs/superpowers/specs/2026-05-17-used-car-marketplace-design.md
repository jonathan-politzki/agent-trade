# Used-Car Marketplace with Asymmetric Information — Design

**Date:** 2026-05-17
**Branch:** `feat/car_exp`
**Author:** Robert (Aganthos) + Claude
**Status:** revised after Codex review (see `2026-05-17-codex-review.md`)
**Design principle (post-review):** *deterministic economic engine + LLM for flavor + replayable ablation*. The headline causal claim (visible-rep vs hidden-rep welfare delta) is reproducible from a fixed seed without re-querying any LLM.

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

### 3.1 Execution modes (orchestrator)

Every scenario runs in one of three modes, switched via `--mode`:

| mode    | seller decisions      | buyer decisions       | LLM calls per run | use for                                  |
|---------|-----------------------|-----------------------|-------------------|------------------------------------------|
| `fast`  | archetype rule        | persona policy rule   | 0                 | sweeps, ablations, CI runs, **the headline chart** |
| `llm`   | LLM (cached output)   | LLM (cached output)   | high, but cached  | recording the LLM-flavored transcripts the demo shows |
| `replay`| read from cache       | read from cache       | 0                 | live demo playback; deterministic, instant |

The `fast` mode is the source of truth for every metric chart. `llm` is run once offline per scenario to record cached transcripts (asking-price prose, negotiation messages, sampled buyer rationales). `replay` is what the audience actually sees on stage — same metrics as `fast`, with LLM-generated prose interleaved as flavor.

This separation removes LLM noise from the causal claim and removes LLM latency from the demo window.

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

### 4.5 Seller archetypes (R1)

Seller dishonesty is not an emergent LLM behavior — it's a pinned policy. This is what makes the visible/hidden ablation identifiable. Three archetypes with fixed population proportions:

| archetype     | share | listing_condition                   | claimed_vhr_flags                 | asking_price                          |
|---------------|-------|-------------------------------------|-----------------------------------|---------------------------------------|
| `honest`      | 60%   | `true_condition`                    | `true_vhr_flags`                  | `seller_ceiling` + ±5% jitter         |
| `moderate`    | 30%   | `min(true_cond + 1.0, 5.0)`          | drops 1 worst flag if present     | `seller_ceiling` + 5–15% markup       |
| `aggressive`  | 10%   | `min(true_cond + 2.0, 5.0)`          | drops all negative flags          | `seller_ceiling` + 10–25% markup      |

```python
@dataclass
class SellerArchetype:
    name: str                # honest | moderate | aggressive
    condition_bias: float    # 0.0, 1.0, 2.0
    vhr_disclosure: str      # full | drop_worst | drop_all_negative
    asking_markup: tuple[float, float]   # (low, high) over seller_ceiling
```

Population draw at run start: 12 honest, 6 moderate, 2 aggressive (k=20). Same archetype draw per `seed` across visible/hidden — ablation compares the *same dishonest population* under different reputation regimes.

**Why pin behavior:** without this, the welfare delta isn't attributable to reputation — it's confounded by stochastic LLM dishonesty. With it, the delta isolates the reputation institution as the causal mechanism.

**Where LLMs still matter (in `llm` mode):**
- Listing description prose conditioned on `(listing_condition, claimed_vhr_flags)` — naturally embellishes for inflater archetypes.
- Negotiation messages (the conversational turns), but the *decision policy* (accept/counter/decline at what price) is rule-based per archetype.
- Sampled live transcript on stage.

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

### 6.2 What buyers see (R3 — reputation in ranking, not just tool)

Two reputation channels, both controlled by `reputation_mode`:

**Channel A — search ranking (the operational channel).** Search results are scored:

```python
score(listing, query) = relevance(listing, query) * (1 + γ * rating_norm(seller))
   where rating_norm = (α / (α + β) - 0.5) * 2   ∈ [-1, 1]   # centred so neutral seller doesn't move score
   and γ = 0.5 in visible mode, 0 in hidden mode
```

In `visible` mode, reputable sellers rise in search rank and disreputable sellers sink. This is what every real platform (CarGurus, eBay, Carfax) does, and it's what makes the welfare delta mechanically attributable to reputation — not to whether agents happened to call a tool.

**Channel B — tool call (instrumentation).** `lookup_seller(seller_id)` is still available to buyers in `visible` mode, returning rating + review count + 3 recent excerpts. The tool's call rate per buyer model is logged as a secondary outcome (does Opus consult reputation more than Haiku?), but the headline chart does not depend on it.

In `hidden` mode, `lookup_seller` is removed from the tool set entirely, and Channel A's γ goes to 0.

### 6.3 Ablation toggle

`reputation_mode ∈ {visible, hidden}`. Same seed → same arrivals, same inventory, same archetype assignments, same buyer policies; only the reputation channels change. (R7: deferred `sock_puppet`, `cold_start`, and `capability_asymmetry` to extended-results runs that ship if time permits.)

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

### 8.2 S2 — m diverse listings, 10 personas (R8: deterministic, no LLMs)

Cut LLM agents from S2 entirely; it's an analytical replication of the paradox-of-choice finding, not a separate live demo. Compare two deterministic buyer policies:

- `first_acceptable`: visit listings in search order, buy first car that beats utility threshold `τ_persona`.
- `full_search`: enumerate all listings, buy the argmax of `U(car, asking_price | persona)`.

Sweep m ∈ {10, 25, 50, 100, 200}, 50 seeds per cell. Output: mean regret-vs-m curve, one line per policy. ~30 lines of code, runs in seconds, no API cost. Backup-slide chart.

(LLM-agent S2 deferred to "extended results" if time remains.)

### 8.3 S3 — Open market, **headline** (R2 + R4 + R7)

#### 8.3.1 Setup

- k=20 sellers (12 honest / 6 moderate / 2 aggressive per §4.5), seeded inventories 3–8 cars each (≈100 cars total).
- m=150 buyers arriving over T=400 simulation steps as Poisson(λ = m/T). Demand > supply by design.
- Up to 5 concurrent open negotiations per seller; 1 per buyer.
- Soft deadline 6 turns per negotiation.
- Search returns top-K=10 by `score()` from §6.2.

#### 8.3.2 Market-clearing rules (R4)

- A **listing is locked** while it has any open offer. Locked listings are excluded from search results.
- A locked listing unlocks on `decline`, `withdraw`, or turn-deadline expiry.
- A seller accepting an offer marks the listing `sold`, withdraws all other open offers on that listing, frees the listing-lock.
- A buyer holding an open offer cannot start another negotiation; she must accept, decline, or time out first.
- Abandoned negotiations (deadline reached without resolution) are logged with `outcome="abandoned"` and contribute zero surplus.

#### 8.3.3 Run modes (R2)

- `--mode fast` (default for chart-producing runs): archetype rule-policies for sellers, persona policies for buyers (utility-maximising with calibrated noise floor), zero LLM calls. ~5 seconds per run on a laptop. **All published metrics come from `fast` mode.**
- `--mode llm` (run once per scenario, offline): same scenario, but listing prose, negotiation messages, and a sampled buyer rationale come from Claude calls. Cached to `runs/{run_id}/llm_cache.jsonl`. Used to produce the on-stage transcript content.
- `--mode replay` (live demo): plays back a previously recorded `llm` run instantly with no API calls.

#### 8.3.4 Headline ablation

`reputation_mode ∈ {visible, hidden}` × same seed × `fast` mode. Bootstrap CIs over 30 seeds (n=30 because runs are 5s each). Welfare delta with 95% CI is the money chart.

#### 8.3.5 Extended results (R7 — run if time, do not block demo)

- Sock-puppet stress: `sock_puppet_p ∈ {0, 0.05, 0.10, 0.20}` injecting fake high ratings on aggressive sellers.
- Cold-start: inject 4 new sellers at t=T/2 with Beta(1,1) prior.
- Capability asymmetry: switch `--mode llm` for selected buyer cohorts mixing Opus/Sonnet/Haiku.

These are backup-slide material. If any block the Saturday-ship critical path, drop them.

## 9. Evaluator

Single module `car_market/evaluator.py`. Consumes the JSONL event log emitted by `Marketplace` (same format as existing `project_deal/marketplace.py`). Produces:

- `runs/{run_id}/metrics.json` — aggregate numbers.
- `runs/{run_id}/per_deal.csv` — every deal with oracle-aware columns.
- `runs/{run_id}/reputation.csv` — per-seller, per-timestep Beta state.
- `runs/{run_id}/figures/` — matplotlib figures (welfare bar, Gini curve, rep trajectory, regret-vs-pool, ablation comparison).

### 9.1 Locked metric formulas (R5)

These formulas are committed contract. The evaluator implements them literally; figures derive from them without reinterpretation.

**Per closed deal** (a `(buyer, seller, car, price)` tuple):

```
buyer_surplus     = U(car | persona) - price
seller_surplus    = price - true_value          # uses oracle, not asking_price
deal_welfare      = buyer_surplus + seller_surplus
condition_premium = price - U_at_listing_cond(car | persona)   # how much buyer overpaid given the inflated claim
honesty_at_deal   = clip(1 - |listing_cond - true_cond| / 2.0, 0, 1)
```

**Per buyer that did not transact** (left market unfilled by t=T):

```
buyer_surplus = 0                              # no penalty; left market in equilibrium
no_deal_flag  = True                           # used for "% buyers served" metric
```

**Per scenario run**:

```
total_welfare       = Σ deal_welfare across all closed deals
mean_buyer_surplus  = mean(buyer_surplus) over BUYERS (no-deal buyers contribute 0)
mean_seller_surplus = mean(per-seller surplus across all closed deals)
surplus_gini        = Gini( per-buyer total surplus )                # inequality of buyer outcomes
seller_lorenz       = Lorenz curve of (deals_per_seller)             # market concentration
mean_regret         = mean over buyers of (U(best_attainable | persona) - U(actually_received | persona))
                      where best_attainable = argmax over listings active during buyer's lifetime
                      that satisfied her hard constraints
rep_convergence_t   = first t such that |α/(α+β) - true_honesty_rate| < 0.1 for ≥80% of sellers
                      (only well-defined for archetype-pinned sellers)
```

**Bootstrap CIs**: n=30 seeds per condition (e.g., visible vs hidden), report mean and 95% bootstrap CI via 1000 resamples of the seed-level means. **No CI reported on fewer than 10 seeds.**

**No-deal handling**: no-deal buyers count as buyer_surplus=0 in averages. They contribute to `% buyers served` but not to `mean_regret` (their counterfactual is also no-deal in the alternative ablation, by same seed).

**Welfare units**: dollars. `seller_floor`/`seller_ceiling` are in dollars; `U` returns a dollar-equivalent (achieved by normalising hedonic weights to sum to a persona's `max_budget` at perfect-match attributes).

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

## 12. Headline demo (Saturday) — R6 revised

Pre-recorded `llm`-mode runs replayed live. The audience sees LLM-flavored transcripts; the metrics chart is pre-computed from the `fast`-mode 30-seed sweep.

```
1. Show one S3 listing card with the LLM-generated description, narrate the     20s
   asymmetry (true_cond=2.5, listing_cond=4 — aggressive seller).
2. Replay S3 visible (cached LLM transcripts, accelerated 10x).                  45s
   Reputation stars visibly shift; aggressive sellers drop in rank.
3. Replay S3 hidden (same seed, same LLM transcripts where they exist).          45s
4. Cut to the welfare-delta bar chart (pre-computed, fast-mode, 30 seeds, CIs). 30s
   "Reputation institution worth $X per transaction, p < 0.01."
5. Show one live LLM negotiation transcript (one buyer, one seller, real time).  60s
   This is the only live LLM call on stage. Picks an aggressive seller for drama.
6. Show S1 heatmap (backup) and S2 regret-vs-m curve (backup) as supporting.     20s
7. Q&A: pitch karma-staked-disclosure as "what we're submitting to NeurIPS".    flex
```

Total stage time ~3.5 min plus Q&A. **The headline chart never depends on a live LLM call.** Step 5 is the one live LLM moment, and if rate limits hit, we replay from cache and apologize — the chart is still on screen.

## 13. Out-of-scope (explicitly)

- Karma-staked-disclosure mechanism (Design C from brainstorm) — Aganthos NeurIPS write-up only.
- Cross-model factorial like Project Deal's 2×2 — collapsible into S3's capability-asymmetry sub-experiment.
- Production Harbor packaging — bonus only after metrics replicate.
- Anything that needs Cox Automotive paid APIs.
- Anything that requires live KBB/Edmunds scraping at runtime.

## 14. Risks and mitigations

| Risk                                              | Likelihood | Mitigation                                                                 |
|---------------------------------------------------|------------|-----------------------------------------------------------------------------|
| API rate limits / cost overrun during S3          | LOW (after R2) | `fast` mode produces all charts; `llm` mode runs once offline; live demo uses `replay` |
| Hedonic calibration drifts → unrealistic prices   | medium     | Cross-check `true_value` vs `kbb_midpoint` for sampled cars in tests; assert distribution |
| Visible/hidden welfare delta turns out small      | medium     | Tune §4.5 archetype shares to ensure visible lemons effect; budget seed-sweep to detect early |
| Archetype-pinned sellers feel "too scripted"      | low        | LLM-flavored prose makes inflation feel organic; live transcript step (12.5) shows the agent reasoning |
| Beta-decay parameter wrong, rep never converges   | low        | Param sweep `DECAY ∈ {0.95, 0.97, 0.99, 1.0}` in offline calibration       |
| Single live LLM call (step 12.5) rate-limits       | low        | Pre-record fallback transcript; have it ready to swap in if API stalls     |

## 15. Decision log

- **2026-05-17**: chose **synthetic generator** over MMR/KBB-as-oracle. Reasons: stale data (Manheim 2015), licensing optics (Cox trademark), demo brittleness (KBB/Edmunds scraping), clean regret math for paper.
- **2026-05-17**: chose **S3 as headline**, S1/S2 as supporting. Reasons: highest visual punch (live reputation), most novel research angle (reputation-ablation), Akerlof-grade narrative.
- **2026-05-17**: chose rebrowser AutoTrader as **anchoring** source, not runtime oracle. Reasons: salePrice is locked but marginals are unrestricted; freshness (2026-04 listings); description text is gold for narrative; no runtime dependency.
- **2026-05-17**: deferred **karma-staked disclosure** to post-hackathon. Reasons: implementation complexity not justified by Saturday timeline; deserves its own paper.
- **2026-05-17 (post-Codex)**: applied R1–R8 revisions. The biggest architectural shift is R2 (`--mode fast|llm|replay`): the headline causal claim is produced by a deterministic, LLM-free `fast`-mode sweep, and the live demo plays back cached LLM-flavored transcripts. Reasons: keeps the welfare-delta chart reproducible and cheap, decouples it from LLM latency / cost / nondeterminism, and lets us run 30 seeds per ablation cell on a laptop in seconds. The LLM still does the work that requires natural language (listing prose, negotiation messages, sampled buyer rationale), just not the work that determines the chart.

## 16. Next step

Revised spec is committed. Next: hand off to `superpowers:writing-plans` to produce the ordered, testable implementation plan from this spec. The implementation plan should sequence the build as follows (writing-plans skill will produce the actual ordering and verification gates):

1. `car_market/generator.py` + `car_market/personas/` + locked metric formulas in tests *first* — these are the contract.
2. `car_market/reputation.py` with property-test-style invariants (Beta posterior bounds, decay monotonicity).
3. `car_market/marketplace.py` extending `project_deal/marketplace.py` with reputation, locks, and search ranking.
4. `car_market/scenarios/s3_open_market.py` with the `--mode fast` path *first*. Get the welfare-delta chart producing numbers before adding LLM code.
5. LLM-mode buyer/seller agents reusing `project_deal/agent.py`. Cache transcripts to disk.
6. Evaluator + figures.
7. Replay mode for the demo.
8. S1 heatmap and S2 deterministic curve (backup slides), only after S3 ships.
9. Anchor scripts last — they're optional polish for the marginals.
