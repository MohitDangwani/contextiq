"""Data quality: the recorded checks for an asset, plus a derived overall
verdict — so "is this dataset trustworthy?" has a direct answer instead
of forcing every caller to re-interpret a list of checks themselves.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Asset, DataQualityCheck
from app.models.enums import QualityCheckStatus


@dataclass
class QualityReport:
    asset_id: str
    quality_score: float | None
    overall_status: str
    checks: list[DataQualityCheck]


def _overall_status(checks: list[DataQualityCheck]) -> str:
    if not checks:
        return "unknown"
    statuses = {c.status for c in checks}
    if QualityCheckStatus.FAIL in statuses:
        return "fail"
    if QualityCheckStatus.WARN in statuses:
        return "warn"
    return "pass"


def check_data_quality(db: Session, asset_id: str) -> QualityReport | None:
    asset = db.get(Asset, asset_id)
    if asset is None:
        return None
    checks = (
        db.query(DataQualityCheck)
        .filter(DataQualityCheck.asset_id == asset_id)
        .order_by(DataQualityCheck.checked_at.desc())
        .all()
    )
    return QualityReport(
        asset_id=asset_id,
        quality_score=asset.quality_score,
        overall_status=_overall_status(checks),
        checks=checks,
    )
