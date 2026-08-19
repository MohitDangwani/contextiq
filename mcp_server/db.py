"""DB session helper for MCP tools.

Mirrors app.config.database.get_db()'s lifecycle (one session per call,
closed when done) but as a plain context manager, since MCP tool
functions are called directly rather than through FastAPI's dependency
injection.
"""
from contextlib import contextmanager
from typing import Iterator

import mcp_server  # noqa: F401  -- runs the sys.path bootstrap
from app.config.database import SessionLocal
from sqlalchemy.orm import Session


@contextmanager
def get_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
