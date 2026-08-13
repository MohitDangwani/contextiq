"""Keyword search over documentation.

This is a deliberate stand-in for Phase 5's semantic (embedding-based)
retrieval — same function signature, so the RAG layer can later swap the
implementation (or add a parallel semantic path) without any caller
(API routes, agent tools, MCP) needing to change.
"""
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Documentation


def search_documentation(
    db: Session, query: str | None = None, asset_id: str | None = None, limit: int = 20
) -> list[Documentation]:
    stmt = db.query(Documentation)
    if query:
        like = f"%{query}%"
        stmt = stmt.filter(or_(Documentation.title.ilike(like), Documentation.content.ilike(like)))
    if asset_id:
        stmt = stmt.filter(Documentation.asset_id == asset_id)
    return stmt.order_by(Documentation.id).limit(limit).all()
