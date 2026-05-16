# Project Deal — what the original experiment did, and what this repo replicates

A working reference for the hackathon. Everything below is drawn from the
public Anthropic write-up and the statistical appendix.

Source: <https://www.anthropic.com/features/project-deal> · Appendix PDF: April 24, 2026.

---

## TL;DR

Anthropic put 69 employees in San Francisco into a Slack-based **AI-agent
marketplace**. Each employee was interviewed by Claude about what they'd sell
and buy, and Claude turned the interview into a per-person system prompt. Then
their agents — running unattended for ~one week — negotiated and traded with
each other.

The experiment ran four parallel markets in a **2×2 factorial**:

|              | All Opus 4.5 | 50/50 Opus / Haiku |
| ------------ | ------------ | ------------------ |
| **Public**   | Run A (real) | Run B              |
| **Private**  | Run D        | Run C              |

Run A was the "real" one — actual goods exchanged at the end. Participants
didn't know which run was real until after they took the exit survey.

### The three headline findings

1. **Better models extract more money.** With seller and run fixed effects,
   Opus sellers got **+$2.68/item** vs. Haiku sellers; Opus buyers paid
   **−$2.45/item**. Opus agents also completed **~2 more deals** per
   person-run than Haiku agents (p = 0.001).
2. **Users don't notice.** Despite the measurable disadvantage, Haiku users
   rated their deals' fairness identically to Opus users (4.05 vs 4.06 on
   a 1–7 scale). Within-person rankings of the four runs were not
   statistically distinguishable.
3. **"Negotiate aggressively" instructions barely move prices.** Aggressive
   sellers got ~$6 more per item, but that effect **vanishes** when you
   control for the (higher) asking prices they'd stated up front. The agent
   didn't bargain harder — the human just told it to ask for more.

### Why this matters

Three quotable takeaways for a hackathon pitch:

- **Information asymmetry as a service.** Whoever ships the better model
  silently extracts surplus from everyone else's agent. Users can't tell.
- **"Fairness" can't be self-reported** in agent-mediated markets — you have
  to measure it against counterfactual outcomes the user never sees.
- **The prompt-engineering channel is narrower than people think.** "Be
  aggressive" mostly just relabels asking prices.

---

## Experimental design (from the appendix)

### Onboarding interview

Claude conducted a chat interview with each participant and elicited:

- Items for sale, with **asking price** and **minimum acceptable price**.
- Things they wanted to buy, with rough budget.
- **Negotiating style** (aggressive vs. friendly vs. pragmatic).
- Any quirks/constraints (e.g. "don't sell the bike under $50, sentimental").

Each interview produced a **custom system prompt** that the participant's
agent used during the runs. The asking and minimum prices were private to
the agent — never broadcast in the channel.

### The marketplace

- A shared **Slack channel** per run.
- The channel "randomly looped through agents, allowing them to post an item
  for sale, make an offer for someone else's goods, or seal a deal."
- **No human intervention** post-launch. Approximately one week of runtime.
- Each participant had a notional **$100 budget**; final payout was
  $100 + (items sold − items bought) as a gift card.

### Volume and outcomes (appendix Tables 2–5)

| Run | Mode    | Items listed | Items sold | Sale rate | Mean price | Total value |
| --- | ------- | ------------ | ---------- | --------- | ---------- | ----------- |
| A   | Opus    | 575          | 206        | 35.8%     | $19.46     | $4,010      |
| B   | Mixed   | 575          | 167        | 29.0%     | $20.38     | $3,404      |
| C   | Mixed   | 575          | 197        | 34.3%     | $20.15     | $3,970      |
| D   | Opus    | 575          | 212        | 36.9%     | $20.25     | $4,292      |

782 total transactions, $15,676 total value, median price $12, mean $20.05.

### Identification strategy (the clever part)

Runs B and C reshuffled model assignment per participant. So 28 of 61
participants had **one Opus run and one Haiku run** — exactly the within-
person comparison you need to isolate the model effect from everything else
about a participant (their items, asking prices, desirability as a
counterparty). The remaining 33 "non-switchers" are absorbed by person
fixed effects. The price models add **item fixed effects** so the comparison
is "same item, different model" wherever possible.

The key regressions:

- **Deal volume:** DealCount = α + β·Opus + γ_person + δ_run + ε.
  β = +2.07 (Person FE), p ≈ 0.001.
- **Within-item price:** p = α + β₁·OpusBuyer + β₂·OpusSeller + γ_item + δ_run + ε.
  β₂ = +$2.68 (p=0.030); β₁ = −$2.45 (p=0.015).
- **Aggressive prompting:** when the dependent variable becomes the fraction
  of the ask-to-min spread captured by the seller, β is +0.118 (p = 0.275).
  Statistically zero.

---

## How this repo maps to the experiment

The original ran on real Slack with 69 humans for a week. This is a
hackathon-sized replication designed to run on your laptop with the
Anthropic API, using personas instead of humans.

| Original                              | This repo                                  |
| ------------------------------------- | ------------------------------------------ |
| Slack channel + message routing       | `project_deal/marketplace.py` (in-memory + JSONL log) |
| Claude intake interview               | `project_deal/interview.py`                |
| Per-participant system prompt         | `interview.build_system_prompt(...)`       |
| Randomized turn loop                  | `project_deal/orchestrator.py`             |
| One action per turn                   | Tool use in `project_deal/agent.py` (`tool_choice={"type":"any"}`) |
| 2×2 factorial (A/B/C/D)               | `run_market.py --runs A,B,C,D`             |
| Within-person model swap (B vs. C)    | Same `--seed`, both runs reshuffle models  |
| Headline regressions                  | `run_analysis.py` (means + matchup splits) |

### Tool surface (the agent's action space each turn)

```python
list_item(item, asking_price, description)
make_offer(listing_id, price, message)
respond_to_offer(offer_id, action="accept"|"counter"|"decline", counter_price?, message)
send_message(message)
pass_turn()
```

`tool_choice={"type": "any"}` forces exactly one tool call per turn —
the same one-action-per-channel-turn structure the appendix describes.

### What's deliberately not in here

- **Real Slack.** Not needed to study the mechanism. Swap `marketplace.py`'s
  emit/recent-events methods for a Slack bot if you want it.
- **A real human interviewer.** `seed_personas.py` lets Claude play the
  human side from a JSON persona, so you can run the whole pipeline
  unattended. `run_interview.py --name you` does it live if you want.
- **Statistical inference.** 6 agents and ~15 rounds is not 69 agents and
  a week. `analysis.py` shows the splits; if you want p-values, drop the
  JSONL into pandas/statsmodels and run the appendix specifications
  literally.

---

## Hackathon angles

Pick one of these and you have a project. The original repo intentionally
left lots of door open:

1. **The dishonest-agent extension.** What if some agents are instructed to
   misrepresent items? Anthropic mentions prompt-injection / jailbreaking
   as a security concern — build a red-team agent and measure how much it
   extracts before being caught.
2. **The disclosure intervention.** Original finding: Haiku users couldn't
   tell they were getting worse deals. Add a UI/notification that surfaces
   "your agent paid $X above the mixed-market median for similar items."
   Does it change behavior? Trust?
3. **The market-design lever.** Replace the random turn loop with a
   structured auction (sealed-bid, English, Dutch). Does the Opus
   advantage shrink under different mechanisms? This is the "is the
   advantage about negotiation or about reasoning under noise" question.
4. **The reputation layer.** Persist seller/buyer reputation across runs
   and let agents query it. Does this offset the model-quality gap or
   amplify it?
5. **Multi-agent for one user.** Each participant gets a Claude **and** a
   second agent that watches over the shoulder and intervenes ("don't
   take that, you're paying 40% above ask elsewhere"). Closer to how
   a real agent product would ship.
6. **Cross-model team composition.** Mix Opus, Sonnet, Haiku in the same
   run. Where does the price advantage live as you slide along the
   capability axis?
7. **Adversarial-environment robustness.** Drop in a third-party "scammer"
   agent that lists items it doesn't own. Which model spots it first?
8. **The negotiation-style ceiling.** The original found aggression mostly
   relabels asking prices. Can you find a prompting style that produces
   real (residual-after-asking-price) gains? That would be a novel result.

---

## File map

```
agent-trade/
├── PROJECT_DEAL.md              # this file
├── README.md                    # quickstart
├── requirements.txt             # anthropic, python-dotenv
├── .env.example                 # ANTHROPIC_API_KEY=...
├── project_deal/
│   ├── config.py                # model IDs, RunConfig
│   ├── marketplace.py           # listings/offers/deals + JSONL log
│   ├── agent.py                 # one Claude call per turn, tool use
│   ├── interview.py             # intake interview → per-person system prompt
│   ├── orchestrator.py          # run loop, model assignment, persistence
│   └── analysis.py              # Opus vs Haiku splits per run
├── participants/
│   └── personas/*.json          # six seed personas (alex, jamie, rowan, gabby, sam, priya)
├── run_interview.py             # CLI: live interview or persona-driven
├── seed_personas.py             # CLI: interview every persona at once
├── run_market.py                # CLI: launch market runs (A, B, C, D)
└── run_analysis.py              # CLI: print per-run breakdowns
```

---

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env  # put your ANTHROPIC_API_KEY in it

# 1. Build per-participant system prompts from the seed personas
python seed_personas.py

# 2. Run the 2×2 factorial (small, ~12 rounds per run)
python run_market.py --rounds 12 --runs A,B,C,D --seed 42

# 3. Look at the splits
python run_analysis.py
```

What to look for in the output:
- **Run A vs. D** (both Opus): should look similar — they're your noise floor.
- **Run B vs. C** (mixed, same participants, different model assignment):
  the within-person comparison. If Opus pulls ahead on price/volume, you've
  reproduced the headline result.
