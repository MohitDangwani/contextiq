from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import schemas
from app.config.database import get_db
from app.services import assets as asset_service
from app.services import business_terms as business_term_service
from app.services import documentation as documentation_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=schemas.SearchResultsOut)
def federated_search(
    q: str = Query(..., min_length=1), limit: int = Query(10, le=50), db: Session = Depends(get_db)
):
    """Search across assets, business terms, and documentation at once —
    a single entry point for a search bar, and a preview of the kind of
    fan-out the agent's tool selection will do later (Phase 7/8)."""
    return schemas.SearchResultsOut(
        assets=asset_service.search_assets(db, query=q, limit=limit),
        business_terms=business_term_service.search_business_terms(db, query=q, limit=limit),
        documentation=documentation_service.search_documentation(db, query=q, limit=limit),
    )
