"""The chat endpoint: a thin HTTP wrapper over app.agent.run.run_agent(),
which is already documented as the one function any interface (API, MCP,
evaluation) should call. No orchestration, grounding, or tool-selection
logic lives here -- this route owns nothing but request/response shape."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.run import run_agent
from app.api import schemas
from app.config.database import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=schemas.ChatResponseOut)
def ask(request: schemas.ChatRequest, db: Session = Depends(get_db)):
    return run_agent(request.question, db=db)
