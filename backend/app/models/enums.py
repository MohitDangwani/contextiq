"""Enumerations shared across models.

Plain Python str-Enums, stored as native Postgres ENUM types via SQLAlchemy.
Kept small and close to what the product actually needs to answer questions
like "which datasets contain PII?" or "is this dataset trustworthy?".
"""
import enum


class AssetType(str, enum.Enum):
    TABLE = "table"
    VIEW = "view"
    DASHBOARD = "dashboard"
    MODEL = "model"


class PIIStatus(str, enum.Enum):
    NONE = "none"
    CONTAINS_PII = "contains_pii"
    UNKNOWN = "unknown"


class QualityCheckStatus(str, enum.Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
