# agent-trade

A small, hackable replication of Anthropic's **Project Deal** experiment
(<https://www.anthropic.com/features/project-deal>): a Slack-style marketplace
where AI agents negotiate and trade on behalf of human participants.

See [`PROJECT_DEAL.md`](./PROJECT_DEAL.md) for what the original experiment
did, what this repo maps to, and a list of hackathon directions.

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env   # put your ANTHROPIC_API_KEY here

# Build per-participant agents from the seed personas (Claude plays each human)
python seed_personas.py

# Run the 2×2 factorial: A/D = all Opus, B/C = mixed Opus/Haiku
python run_market.py --rounds 12 --runs A,B,C,D --seed 42

# Inspect Opus-vs-Haiku splits
python run_analysis.py
```

Want to interview yourself live instead of using a persona:

```bash
python run_interview.py --name your_name
```

Then drop a `your_name.json` into `participants/generated/` (it's saved there
automatically) and re-run the market.

## How it works

- `seed_personas.py` runs Claude as an interviewer against each persona,
  extracts a structured profile, and builds a per-agent system prompt.
- `run_market.py` opens four marketplaces and randomly cycles turns. Each
  turn one agent gets exactly one tool call: list an item, make/respond to
  an offer, post a message, or pass.
- All events stream to `runs/<run>/events.jsonl`; final deals land in
  `runs/<run>/summary.json`.

## Layout

```
project_deal/
  marketplace.py    # listings, offers, deals, event log
  agent.py          # one-turn agent (Anthropic API + tools)
  interview.py      # intake → profile → custom system prompt
  orchestrator.py   # run loop, model assignment, JSONL persistence
  analysis.py       # Opus vs Haiku splits

participants/personas/   # seed personas (edit / add your own)
run_*.py                 # CLI entrypoints
```
