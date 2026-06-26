"""Report agent — turns pre-computed daily metrics into a management summary."""
from __future__ import annotations

import json
from typing import Any

from app.llm.base import LLMClient
from app.prompts import load_prompt


def run_daily_report(metrics: dict[str, Any], llm: LLMClient) -> str:
    system = load_prompt("daily_report")
    user = "Metrics (JSON):\n" + json.dumps(metrics, indent=2)
    return llm.complete(system=system, user=user, max_tokens=1500).strip()
