"""Utilities for cleaning up and interpreting raw LLM output."""
import json
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


# Generic phrasings the agent uses when it's flagging that something isn't
# available -- a full abstention ("I could not find...") or a named gap
# within an otherwise-answered question ("...but that isn't documented").
# Domain-agnostic on purpose: no dataset name, business term, or benchmark
# question appears here, only the shape of language SYSTEM_PROMPT
# (app/agent/graph.py) is tuned to produce for "I don't have this".
#
# IMPORTANT: this is a MEASUREMENT tool, not an enforcement one. It powers
# the Phase 10 harness's deterministic abstention metric and test
# assertions -- it does NOT decide what the agent is allowed to answer.
# That guarantee is app.agent.grounding.verify_support() (a structured,
# code-enforced check), specifically because phrase-matching a model's
# free-text wording is too brittle to be a safety-critical mechanism --
# this list has already needed three corrections this project for exactly
# that reason. Never wire this into the runtime answer-acceptance path.
GAP_PHRASES = (
    "could not find",
    "couldn't find",
    "cannot find",
    "can't find",
    "unable to find",
    "don't have access to",
    "do not have access to",
    "does not exist",
    "doesn't exist",
    "no documentation",
    "not documented",
    "no record of",
    "not available",
    "not tracked",
    "cannot provide",
    "can't provide",
    "unable to provide",
    "no information",
    "unable to answer",
    "no such",
)

# "don't/doesn't have {enough|any|} information" is the single most common
# gap-phrase family observed, and its middle word varies freely ("enough",
# "any", or nothing) -- one narrow regex for this specific family covers
# all of those at once, instead of chasing each wording into GAP_PHRASES
# one at a time. Deliberately narrow (anchored on "have ... information",
# not a general negation detector) so it doesn't start matching ordinary
# domain sentences like "No, the orders dataset...".
_HAVE_INFO_GAP_RE = re.compile(
    r"\b(don'?t|do not|doesn'?t|does not)\s+have\s+(enough\s+|any\s+)?information\b",
    re.IGNORECASE,
)


def flags_gap(text: str) -> bool:
    """True if `text` explicitly communicates that something wasn't found
    / isn't available -- whether that's the whole answer (a full
    abstention) or just a named gap inside a partially-answered one."""
    if not text:
        return False
    lowered = text.lower()
    if _HAVE_INFO_GAP_RE.search(lowered):
        return True
    return any(p in lowered for p in GAP_PHRASES)


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_object(text: str | None) -> dict | None:
    """Pull the first {...} block out of a model response and parse it.
    Shared by every LLM call in this codebase that asks for a structured
    JSON verdict (the Phase 10 judge, the grounding verifier) instead of
    each keeping its own copy of the same defensive regex-then-parse
    logic. Returns None on anything unparseable -- callers decide their
    own fail-safe default; this function never raises."""
    if not text:
        return None
    match = _JSON_BLOCK_RE.search(strip_thinking(text))
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
