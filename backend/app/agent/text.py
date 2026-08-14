"""Utilities for cleaning up raw LLM output."""
import re

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_UNCLOSED_THINK_RE = re.compile(r"<think>.*$", re.DOTALL | re.IGNORECASE)


def strip_thinking(text: str | None) -> str:
    """Remove Qwen3-style <think>...</think> reasoning blocks.

    Verified against the raw Ollama API (not just langchain-ollama):
    calling /api/chat directly with "think": false still leaked a
    <think> block into the response `content` field. langchain-ollama's
    ChatOllama integration was separately verified to already keep
    `content` clean in both the tool-call and final-answer cases, but
    this is applied everywhere LLM output becomes user-facing text
    anyway -- defense in depth, not reliance on one library's current
    behavior. See docs/agent.md.
    """
    if not text:
        return ""
    cleaned = _THINK_BLOCK_RE.sub("", text)
    cleaned = _UNCLOSED_THINK_RE.sub("", cleaned)
    return cleaned.strip()
