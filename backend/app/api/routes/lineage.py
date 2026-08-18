"""Whole-catalog lineage graph endpoint, separate from the existing
per-asset traversal at /api/assets/{asset_id}/lineage. Own router (not
nested under assets) so "/graph" can't collide with the "/{asset_id}"
path pattern there."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import schemas
from app.config.database import get_db
from app.services import lineage as lineage_service

router = APIRouter(prefix="/lineage", tags=["lineage"])


@router.get("/graph", response_model=schemas.LineageGraphOut)
def get_lineage_graph(db: Session = Depends(get_db)):
    return lineage_service.get_full_graph(db)
