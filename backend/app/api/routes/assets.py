from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import schemas
from app.config.database import get_db
from app.models.enums import AssetType
from app.services import assets as asset_service
from app.services import documentation as documentation_service
from app.services import lineage as lineage_service
from app.services import quality as quality_service

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[schemas.AssetSummaryOut])
def list_assets(
    q: str | None = Query(None, description="Keyword search over asset name/description."),
    domain: str | None = None,
    asset_type: AssetType | None = None,
    tag: str | None = None,
    pii_only: bool = False,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    return asset_service.search_assets(
        db, query=q, domain=domain, asset_type=asset_type, tag=tag, pii_only=pii_only, limit=limit
    )


@router.get("/{asset_id}", response_model=schemas.AssetDetailOut)
def get_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
    return asset


@router.get("/{asset_id}/schema", response_model=list[schemas.ColumnOut])
def get_asset_schema(asset_id: str, db: Session = Depends(get_db)):
    columns = asset_service.get_schema(db, asset_id)
    if columns is None:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
    return columns


@router.get("/{asset_id}/owner", response_model=schemas.OwnerOut)
def get_asset_owner(asset_id: str, db: Session = Depends(get_db)):
    asset = asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
    if asset.owner is None:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' has no recorded owner.")
    return asset.owner


@router.get("/{asset_id}/lineage", response_model=schemas.LineageOut)
def get_asset_lineage(
    asset_id: str,
    direction: str = Query("both", pattern="^(upstream|downstream|both)$"),
    db: Session = Depends(get_db),
):
    result = lineage_service.get_lineage(db, asset_id, direction=direction)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
    return result


@router.get("/{asset_id}/quality", response_model=schemas.QualityReportOut)
def get_asset_quality(asset_id: str, db: Session = Depends(get_db)):
    result = quality_service.check_data_quality(db, asset_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
    return result


@router.get("/{asset_id}/documentation", response_model=list[schemas.DocumentationOut])
def get_asset_documentation(asset_id: str, db: Session = Depends(get_db)):
    asset = asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
    return documentation_service.search_documentation(db, asset_id=asset_id)
