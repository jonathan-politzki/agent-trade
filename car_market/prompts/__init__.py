from pathlib import Path


_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a prompt template by stem name (e.g. 'listing_description')."""
    p = _DIR / f"{name}.md"
    return p.read_text()
