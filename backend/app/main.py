"""
ContextIQ backend entrypoint.

The context/query API (Phase 4) is wired in here. The agent, RAG, MCP,
and evaluation endpoints (chat, /api/evaluation/run) are not built yet —
see docs/architecture.md for the phase plan.
"""
from fastapi import FastAPI

from app.api.routes import api_router

app = FastAPI(
    title="ContextIQ",
    description="AI-powered enterprise data intelligence agent",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
