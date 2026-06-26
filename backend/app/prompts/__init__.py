"""Prompt templates, stored as files and loaded by name.

Keeping prompts out of code makes them easy to review and tune. Each agent
loads its system prompt via `load_prompt("<name>")`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


@lru_cache
def load_prompt(name: str) -> str:
    path = _PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
