# RAG (Retrieval-Augmented Generation)

## The problem

Structured questions ("who owns orders?", "show me the schema") are
already answered exactly by the Phase 4 context services — direct SQL
against typed columns. But questions like "what does customer lifetime
value mean?" or "how is revenue recognized?" live in free text
(`documentation`, `business_terms`), phrased differently than however
the user asks. RAG is what lets those get answered by *meaning*, not
exact keyword match.

## Pipeline

```
Documentation / BusinessTerm rows (Postgres, from Phase 3)
        |
        v
chunk_text()            app/rag/chunking.py
  - split on markdown ## headers (topic-coherent chunks)
  - sliding window for any section still too long
        |
        v
embed_batch()            app/rag/embeddings.py
  - sentence-transformers/all-MiniLM-L6-v2, 384-dim, local
        |
        v
document_chunks table    app/models/chunk.py (pgvector `vector(384)` column)
  - each row: content + embedding + denormalized title/asset_id/source_url
        |
        v
semantic_search()        app/rag/retrieval.py
  - embed the query, ORDER BY embedding <=> query_vector (cosine distance)
  - returns RetrievedChunk: content + similarity + full source citation
```

Two scripts drive this, mirroring `scripts/seed_database.py`'s pattern:
- `scripts/ingest_documents.py` — clears and rebuilds `document_chunks`
  from the current `documentation`/`business_terms` rows.
- `scripts/test_retrieval.py` — a small, hand-written set of known
  questions checked against expected source documents.

## Why chunks are their own table, not columns on Documentation

`document_chunks` is a rebuildable *index*, not source data. Re-running
ingestion (different chunk size, different embedding model) never
touches `documentation` or `business_terms` — those stay the single
source of truth. This mirrors the split already documented for
`Documentation.content` in Phase 2/3: source text and retrieval index
are different concerns.

## Every chunk carries its own citation

`title`, `asset_id`, and `source_url` are denormalized directly onto
each `DocumentChunk` row specifically so a retrieved chunk is
self-describing — no join is needed to answer "where did this come
from?", and the agent (Phase 7+) can cite it directly rather than just
asserting an answer.

## Embedding provider: local, not OpenAI

The original tech stack called for an LLM API for embeddings. No
`OPENAI_API_KEY` was available in this environment, so — by explicit
choice, not a silent fallback — this phase uses a free local model
(`sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions) instead. The
whole pipeline runs offline with no per-call cost. The tradeoff: it's a
smaller, less capable embedding space than a hosted model like OpenAI's
`text-embedding-3-small` (1536-dim) — retrieval quality is good but not
as sharp on subtle paraphrasing (see the verification results below).

Swapping providers later touches exactly two places: `EMBEDDING_DIM` in
`app/models/chunk.py` and the implementation of `embed_batch()` in
`app/rag/embeddings.py`. Nothing in `chunking.py` or `retrieval.py`
depends on which model produced the vectors — then re-run
`scripts/ingest_documents.py`.

## Verification against live Postgres + pgvector

`scripts/ingest_documents.py` produced 22 chunks (20 from 5 documentation
files, 2 from the 2 business terms) in the real `document_chunks` table,
confirmed directly via `psql`.

`scripts/test_retrieval.py` ran 10 hand-written questions against
`semantic_search()`, checking whether the expected source document
appeared in the top 3 results: **10/10 (100%) hit-rate@3**. One case is
worth being honest about: "What team maintains the customers dataset?"
matched *PII Handling Policy* as its top-1 result (similarity 0.46, a
weak match) with the expected *Customers Dataset Overview* only at
rank 2 — a real limitation of the small local embedding model on
paraphrased queries, not a bug, and exactly the kind of thing hit-rate@3
(rather than @1) is designed to tolerate. A hosted embedding model would
likely do better here.

Also verified: filtering by `asset_id` correctly excludes semantically
related chunks from other assets (a query scoped to `revenue_dashboard`
never returned `Revenue Recognition Policy` chunks, even though they're
topically close, because those are tagged `asset_id=revenue_model`).

## Not yet wired up

`app/rag/retrieval.py` is not called from `app/api` or `app/services` —
per this phase's scope, RAG stays a standalone layer. It becomes a tool
the agent can call starting in Phase 7/8.
