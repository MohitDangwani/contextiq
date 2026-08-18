"""
ContextIQ backend entrypoint.

The context/query API (Phase 4) and the chat endpoint wrapping the
LangGraph agent (Phase 11, app.api.routes.chat) are wired in here. MCP and
the evaluation-run endpoint are not built as HTTP routes yet — see
docs/architecture.md for the phase plan.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.config.settings import settings

app = FastAPI(
    title="ContextIQ",
    description="AI-powered enterprise data intelligence agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
