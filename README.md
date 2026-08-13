# ContextIQ — AI-Powered Enterprise Data Intelligence Agent

> Status: Phase 1 (architecture scaffold) complete. Full documentation
> (setup, API reference, evaluation results, etc.) will be filled in as
> each phase lands — see docs/architecture.md for the phase plan.

## What is this?

ContextIQ is a prototype AI agent that answers natural-language questions
about enterprise datasets — "Which datasets contain PII?", "Where does
monthly revenue come from?", "Who owns customer_orders?" — by grounding
its answers in real metadata, business definitions, lineage, data-quality
signals, and documentation, instead of hallucinating.

It's built as a portfolio project to demonstrate the skills behind an
AI-native builder role: RAG, embeddings, vector search, agentic tool use
with LangGraph, MCP, metadata/context modeling, data lineage, and
evaluation of AI agents — on top of a clean Python/FastAPI/Postgres stack.

## Project layout

See [docs/architecture.md](docs/architecture.md) for the full explanation
of the structure and the phase-by-phase build order.
