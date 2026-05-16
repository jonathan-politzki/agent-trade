"""CLI: interview a participant (either live or by playing a scripted persona).

Usage:
  python run_interview.py --name alex                    # live: you answer the questions
  python run_interview.py --persona participants/personas/alex.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic

from project_deal.interview import interview_and_save


def main() -> None:
    load_dotenv(override=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", help="Participant name (live mode).")
    ap.add_argument("--persona", help="Path to a persona JSON; Claude plays them.")
    ap.add_argument("--out", default="participants/generated", help="Output directory.")
    args = ap.parse_args()

    client = Anthropic()
    out_dir = Path(args.out)

    if args.persona:
        persona = json.loads(Path(args.persona).read_text())
        interview_and_save(client, persona["name"], out_dir, persona=persona)
    else:
        assert args.name, "Pass --name for live interview or --persona for scripted."
        interview_and_save(client, args.name, out_dir, human_input=input)


if __name__ == "__main__":
    main()
