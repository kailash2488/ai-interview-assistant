"""Versioned prompt templates live in app/prompts/*.md as `SYSTEM text ---USER--- user text`."""
import re
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"
_SEPARATOR = "---USER---"


def load_prompt(name: str) -> tuple[str, str]:
    raw = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    system, _, user = raw.partition(_SEPARATOR)
    if not user:
        raise ValueError(f"Prompt '{name}' is missing the {_SEPARATOR} separator")
    return system.strip(), user.strip()


def wrap_document(text: str, tag: str = "document") -> str:
    """Delimit untrusted text so the model treats it as data. Strips look-alike delimiters."""
    safe = re.sub(rf"</?\s*{tag}\s*>", "", text, flags=re.IGNORECASE)
    return f"<{tag}>\n{safe}\n</{tag}>"


def render(name: str, **blocks: str) -> tuple[str, str]:
    system, user = load_prompt(name)
    for key, value in blocks.items():
        user = user.replace("{{" + key + "}}", value)
    return system, user
