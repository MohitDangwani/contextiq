from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import schemas
from app.config.database import get_db
from app.services import documentation as documentation_service

router = APIRouter(prefix="/documentation", tags=["documentation"])


@router.get("/search", response_model=list[schemas.DocumentationOut])
def search_documentation(
    q: str | None = Query(None, description="Keyword search over title/content."),
    asset_id: str | None = None,
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    return documentation_service.search_documentation(db, query=q, asset_id=asset_id, limit=limit)
