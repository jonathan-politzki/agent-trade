"""Generate participant profiles from every persona under participants/personas/.

Lets you skip live interviews and get straight to a market run:

  python seed_personas.py
  python run_market.py --rounds 12
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic

from project_deal.interview import interview_and_save


def main() -> None:
    load_dotenv(override=True)
    client = Anthropic()
    out_dir = Path("participants/generated")
    out_dir.mkdir(parents=True, exist_ok=True)

    personas_dir = Path("participants/personas")
    for persona_path in sorted(personas_dir.glob("*.json")):
        import json
        persona = json.loads(persona_path.read_text())
        target = out_dir / f"{persona['name']}.json"
        if target.exists():
            print(f"skip {persona['name']} (already generated)")
            continue
        print(f"\n--- interviewing {persona['name']} ---")
        interview_and_save(client, persona["name"], out_dir, persona=persona)


if __name__ == "__main__":
    main()
