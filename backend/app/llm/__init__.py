"""LLM provider abstraction.

The rest of the app depends only on the `LLMClient` interface and obtains a
concrete client via `get_llm()`. Swapping providers is a config change, never a
code change in the agents.
"""
from app.llm.base import LLMClient
from app.llm.factory import get_llm

__all__ = ["LLMClient", "get_llm"]
