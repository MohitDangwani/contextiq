"""Business term definitions ("what does customer_lifetime_value mean?").

Kept separate from asset/schema lookups because a user asking about a
term usually doesn't know (or care) which dataset's column it's attached
to — this lets that question be answered directly, by term name alone.
"""
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import BusinessTerm


def get_business_definition(db: Session, term: str) -> BusinessTerm | None:
    """Case-insensitive exact match on the term name."""
    return db.query(BusinessTerm).filter(BusinessTerm.term.ilike(term)).one_or_none()


def search_business_terms(db: Session, query: str, limit: int = 20) -> list[BusinessTerm]:
    """Keyword search across term name and definition, for when the
    caller doesn't know the exact term."""
    like = f"%{query}%"
    return (
        db.query(BusinessTerm)
        .filter(or_(BusinessTerm.term.ilike(like), BusinessTerm.definition.ilike(like)))
        .order_by(BusinessTerm.term)
        .limit(limit)
        .all()
    )
