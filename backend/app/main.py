"""
ContextIQ backend entrypoint.

This is a placeholder for Phase 1 (architecture only). Real API routes,
the agent, and tool wiring are added in later phases (see docs/architecture.md
for the phase plan). For now this just proves the FastAPI app boots.
"""
from fastapi import FastAPI

app = FastAPI(
    title="ContextIQ",
    description="AI-powered enterprise data intelligence agent",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
