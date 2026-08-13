# Architecture

## The problem

Enterprise data teams field the same questions over and over: "what does
this metric mean?", "who owns this table?", "can I trust this data?",
"where does this number come from?". The answers live scattered across
data catalogs, wikis, Slack threads, and people's heads. ContextIQ is a
prototype of an agent that centralizes that context (metadata, business
definitions, lineage, quality, docs) and answers those questions in
natural language, citing exactly where each answer came from.

## High-level flow

```
User question
     |
     v
FastAPI  /api/chat
     |
     v
LangGraph agent  --(decides which tools are needed)-->  Tool layer
     |                                                        |
     |                                                        v
     |                                          Context services (search,
     |                                          metadata, lineage, quality,
     |                                          ownership, docs) + RAG
     |                                          (embeddings / pgvector)
     |                                                        |
     v                                                        v
Grounded answer + sources + tool activity  <-------------------
```

The **MCP server** is a thin adapter in front of the same context
services — it lets any MCP-compatible client (e.g. Claude Desktop) use
ContextIQ's capabilities directly, without going through the chat agent.

## Why this shape

- **Context services are the single source of truth.** Both the LangGraph
  agent's tools and the MCP server call the same Python service functions
  in `backend/app/services/`, which talk to Postgres. No business logic is
  duplicated between the API, the agent, and MCP — see Phase 9 for why
  this matters.
- **The agent doesn't have unrestricted DB access.** It only sees the
  tools in `backend/app/tools/`, each with a narrow, typed contract. This
  keeps behavior predictable and makes tool selection something we can
  evaluate (Phase 10).
- **RAG is separate from structured lookups.** Structured questions
  ("who owns X", "show me the schema") are answered by direct DB
  queries via context services — fast and exact. Fuzzy questions
  ("what does customer_lifetime_value mean") go through embeddings +
  vector search over documentation and business definitions. The agent
  decides which path (or both) a question needs.

## Repository structure

```
contextiq/
├── backend/            FastAPI app: API, agent, context services, RAG, tools
│   ├── app/
│   │   ├── api/         HTTP routes (Phase 6/10)
│   │   ├── agent/       LangGraph graph: intent -> tool calls -> answer (Phase 7)
│   │   ├── context/     Context-layer domain logic (Phase 2/4)
│   │   ├── rag/         Chunking, embeddings, retrieval (Phase 5)
│   │   ├── tools/       Agent tool definitions (Phase 8)
│   │   ├── models/      SQLAlchemy ORM models (Phase 2)
│   │   ├── services/    Shared service layer used by API, agent, MCP (Phase 4)
│   │   ├── evaluation/  Evaluation harness internals (Phase 10)
│   │   ├── config/      Settings, env loading
│   │   └── main.py      FastAPI app entrypoint
│   └── tests/
│
├── mcp_server/          MCP adapter over the same services (Phase 9)
├── frontend/             React + Vite chat UI (Phase 11/12)
├── data/
│   ├── raw/              Sample e-commerce CSVs (Phase 3)
│   ├── metadata/          Asset/column metadata, ownership, tags, PII, quality
│   ├── lineage/           Dataset lineage relationships
│   ├── documentation/     Free-text docs used for RAG
│   └── evaluation/        Benchmark questions + results (Phase 10)
├── scripts/              seed_database.py, ingest_documents.py, run_evaluation.py
├── docs/                 This file + agent.md, rag.md, mcp.md, evaluation.md
├── docker-compose.yml
├── .env.example
└── README.md
```

## Build order and why

The system is built bottom-up: data model first, then the services that
read it, then retrieval, then the agent that orchestrates both, then the
interfaces (API/MCP/frontend) on top, then evaluation and hardening last.
Each phase depends on the one before it being real and tested — there's
no point building an agent that calls tools backed by services that don't
exist yet. See the main project instructions / conversation history for
the full 17-phase order; each phase's docs and code land with an
explanation before the next phase starts.

## How I'd explain this in an interview

"ContextIQ separates *context* (what do we know about our data — metadata,
lineage, quality, definitions) from *access* (how do you get an answer —
structured queries vs. semantic search) from *orchestration* (which tool
does this question need). The agent is a thin LangGraph graph over a set
of narrow tools; the tools and the MCP server both sit on one shared
service layer so there's exactly one place that knows how to, say, fetch
lineage for an asset. That's what makes it evaluable and debuggable: every
answer can be traced back to specific tool calls and specific rows/docs."
