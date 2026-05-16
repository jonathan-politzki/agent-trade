# Codex Review of Used-Car Marketplace Spec

**Date:** 2026-05-17
**Reviewer:** OpenAI Codex (via MCP) as principal-engineer reviewer
**Spec reviewed:** `2026-05-17-used-car-marketplace-design.md` (v1, pre-revision)
**Verdict:** NEEDS WORK

---

## Verdict (verbatim)

**NEEDS WORK**

The core idea is strong enough to ship: synthetic oracle + private condition + reputation ablation can absolutely produce the headline Akerlof-style demo. But the current spec is too broad and under-specified in exactly the places that determine whether Saturday's live result is reliable. I would not sign off until S3 is made deterministic, cheaper, and more causally controlled.

## Correctness

The generator can support the claims, but only if seller dishonesty is explicitly parameterized. Right now Sections 4.3, 6, and 8.3 imply asymmetry, but they do not define seller types or lying behavior. If sellers are just LLMs deciding organically whether to inflate condition, the demo result is not identifiable. You need something like `seller_type ∈ {honest, moderate_inflater, aggressive_inflater}` with fixed probabilities and deterministic bounds on `listing_condition - true_condition`.

The Beta reputation update is directionally fine, but it is not enough by itself. Buyers must either observe reputation in ranking or reliably use `lookup_seller`. Measuring whether agents call the tool is interesting research, but it is too risky for the money chart. For Saturday, reputation should affect search ranking directly in visible mode, while the agent-facing tool is secondary evidence.

S3 Poisson scheduling will produce activity, but not necessarily a clean welfare delta. With m=150, k=20, about 100 cars, parallel negotiations, and LLM variability, the visible/hidden comparison may differ because of timing contention, not reputation. Same seed helps, but only if arrival order, inventory, seller behavior, and buyer choice policy are replayable across modes.

## Completeness Gaps

The biggest missing piece is a runnable demo contract. Section 12 says live S3 visible and hidden each take 90s, but Section 8.3 implies thousands of tool/LLM turns. There is no call budget, timeout policy, retry policy, cache/replay mode, or fallback if one provider stalls.

The spec also needs explicit market-clearing rules. What happens if two buyers propose on the same listing? Is inventory reserved during negotiation? Can sellers accept multiple offers? When does a listing disappear? How are abandoned negotiations logged? These edge cases will decide whether `per_deal.csv`, welfare, and reputation trajectories are credible.

The evaluator is underspecified for welfare. Section 9 should define exact formulas for buyer surplus, seller surplus, regret, failed-search penalty, and whether welfare includes no-deal buyers. Otherwise the headline chart can be attacked as arbitrary.

## Simplicity

Cut aggressively. For six days solo, Section 8.3 has four sub-experiments; only one is essential.

**Keep:**
- S3 visible vs hidden, same seed.
- One synthetic generator.
- One evaluator producing welfare, regret, deals per seller, reputation trajectory.
- Optional S1 heatmap if already cheap.

**Cut or defer:**
- `sock_puppet_p`
- cold start
- capability asymmetry
- S2 paradox-of-choice
- LLM-generated negative reviews
- real description template extraction unless already done
- `scikit-learn` calibration if a hand-tuned hedonic model gives stable values

The live demo should be a deterministic simulation with a small number of LLM-visible negotiations, not a fully live 150-buyer LLM market.

## Largest Risks

The Saturday-killer is LLM latency/cost/brittleness in S3. 150 buyers × 6 turns × seller responses × tool calls × two ablations can easily exceed the live window and produce nondeterministic outcomes.

Second risk: agents ignore reputation or behave too noisily, making the visible/hidden delta weak. Do not make the core demo depend on emergent tool use.

Third risk: the synthetic market accidentally fails to create lemons. If dishonest sellers are not numerous, cheap, and attractive enough under hidden reputation, reputation will not visibly improve welfare.

## Alternatives

Do not reconsider KBB/MMR. Synthetic is the right choice for the headline-demo goal.

The better approach is a hybrid simulation:

- Deterministic economic engine for all market mechanics and metrics.
- LLM agents used for listing copy, negotiation flavor, and a few sampled transcript panels.
- Reputation directly affects ranking/choice in visible mode.
- Same seed replay for visible vs hidden.

That gives you a reliable money chart while still demoing LLM buyers/sellers.

## Top Changes I'd Require

1. **Section 8.3 / `car_market/scenarios/s3_open_market.py`: replace full live LLM S3 with replayable simulation mode.**
   Add `--mode fast|llm|replay`. The Saturday default should be `fast`, with cached/sample LLM transcripts displayed as supporting evidence.

2. **Section 4.3 / `car_market/generator.py`: add explicit seller honesty model.**
   Add fields like `seller_type`, `condition_bias`, `disclosure_policy`. Example: honest sellers list true condition; inflaters add +1 or +2 capped at 5; aggressive sellers hide negative VHR flags.

3. **Section 6.2 / `car_market/marketplace.py`: make reputation operational, not optional.**
   In `visible` mode, search ranking should include reputation. In `hidden` mode, remove reputation from ranking and tools. Keep `lookup_seller` logging, but do not let the headline result depend on voluntary tool calls.

4. **Section 9 / `car_market/evaluator.py`: lock metric formulas now.**
   Define buyer surplus, seller surplus, total welfare, regret, no-deal handling, and bootstrap CI inputs. The chart should be reproducible from JSONL without interpretation.

5. **Section 12: cut the live demo scope.**
   Demo only: S3 visible replay, S3 hidden replay, side-by-side welfare delta, one live sampled negotiation transcript. Move S1/S2/sock-puppet/cold-start/capability asymmetry to backup slides or post-hackathon.

I'd ship this after those changes. The concept is good; the current spec just gives too much control to stochastic LLM behavior and too little control to the causal mechanism that needs to win the room.

---

## Response

Author agrees with all 5 required changes plus pushes back lightly on three secondary cuts:
- Keep S2 as a *thin* 30-line analytical sub-experiment (no LLMs) so the paradox-of-choice result is preserved as a backup-slide chart.
- Keep `lookup_seller` as instrumentation alongside reputation-in-ranking, since the dual mechanism is cheap and informative.
- Keep one live LLM negotiation transcript in the demo for narrative.

Concrete spec revisions (R1–R8) applied in the next commit. See the design doc for the revised sections.
