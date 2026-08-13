from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import schemas
from app.config.database import get_db
from app.services import business_terms as business_term_service

router = APIRouter(prefix="/business-terms", tags=["business-terms"])


@router.get("", response_model=list[schemas.BusinessTermOut])
def search_business_terms(
    q: str = Query(..., min_length=1), limit: int = Query(20, le=100), db: Session = Depends(get_db)
):
    return business_term_service.search_business_terms(db, query=q, limit=limit)


@router.get("/{term}", response_model=schemas.BusinessTermOut)
def get_business_term(term: str, db: Session = Depends(get_db)):
    result = business_term_service.get_business_definition(db, term)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No business term found matching '{term}'.")
    return result
