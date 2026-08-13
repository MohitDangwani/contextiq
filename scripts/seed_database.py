"""Seed ContextIQ's Postgres database with sample Brightcart (fictional
e-commerce company) data.

Two separate things get loaded, deliberately kept apart:

  1. data/raw/*.csv -> a `raw` Postgres schema, standing in for the
     company's actual operational warehouse. This is real, queryable data
     (e.g. `SELECT * FROM raw.orders`) — it's what the future run_sql
     agent tool (Phase 8) will query.

  2. data/metadata/*.yaml, data/lineage/lineage.yaml, data/documentation/*.md
     -> the catalog tables from app.models (Asset, DatasetColumn, Owner,
     Tag, BusinessTerm, LineageEdge, DataQualityCheck, Documentation).
     This is ContextIQ's own knowledge ABOUT the raw data — metadata, not
     the data itself. This is what the context services (Phase 4) and
     agent tools (Phase 8) will actually query to answer questions.

Re-running this script is safe: it drops and rebuilds the `raw` schema,
and clears + reloads every catalog table.

Usage:
    python scripts/seed_database.py
"""
import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

import yaml
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config.database import SessionLocal, engine
from app.models import (
    Asset,
    Base,
    BusinessTerm,
    DataQualityCheck,
    DatasetColumn,
    Documentation,
    LineageEdge,
    Owner,
    Tag,
)
from app.models.enums import AssetType, PIIStatus, QualityCheckStatus

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
METADATA_DIR = DATA_DIR / "metadata"
LINEAGE_FILE = DATA_DIR / "lineage" / "lineage.yaml"
DOCS_DIR = DATA_DIR / "documentation"


# ---------------------------------------------------------------------------
# Raw schema: the pretend operational warehouse
# ---------------------------------------------------------------------------

RAW_TABLES = {
    "marketing_campaigns": {
        "ddl": """
            CREATE TABLE raw.marketing_campaigns (
                campaign_id INTEGER PRIMARY KEY,
                campaign_name TEXT NOT NULL,
                channel TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                budget NUMERIC NOT NULL
            )
        """,
        "columns": ["campaign_id", "campaign_name", "channel", "start_date", "end_date", "budget"],
        "types": [int, str, str, date, date, float],
    },
    "customers": {
        "ddl": """
            CREATE TABLE raw.customers (
                customer_id INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                signup_date DATE NOT NULL,
                country TEXT NOT NULL,
                acquisition_campaign_id INTEGER REFERENCES raw.marketing_campaigns(campaign_id),
                lifetime_value NUMERIC NOT NULL
            )
        """,
        "columns": [
            "customer_id", "first_name", "last_name", "email", "phone",
            "signup_date", "country", "acquisition_campaign_id", "lifetime_value",
        ],
        "types": [int, str, str, str, str, date, str, int, float],
    },
    "products": {
        "ddl": """
            CREATE TABLE raw.products (
                product_id INTEGER PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                brand TEXT NOT NULL,
                unit_cost NUMERIC NOT NULL,
                list_price NUMERIC NOT NULL,
                is_active BOOLEAN NOT NULL
            )
        """,
        "columns": ["product_id", "product_name", "category", "brand", "unit_cost", "list_price", "is_active"],
        "types": [int, str, str, str, float, float, bool],
    },
    "orders": {
        "ddl": """
            CREATE TABLE raw.orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES raw.customers(customer_id),
                order_date TIMESTAMP NOT NULL,
                status TEXT NOT NULL,
                shipping_address TEXT NOT NULL,
                total_amount NUMERIC NOT NULL,
                source_channel TEXT NOT NULL
            )
        """,
        "columns": [
            "order_id", "customer_id", "order_date", "status",
            "shipping_address", "total_amount", "source_channel",
        ],
        "types": [int, int, datetime, str, str, float, str],
    },
    "order_items": {
        "ddl": """
            CREATE TABLE raw.order_items (
                order_item_id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES raw.orders(order_id),
                product_id INTEGER NOT NULL REFERENCES raw.products(product_id),
                quantity INTEGER NOT NULL,
                unit_price NUMERIC NOT NULL,
                discount_amount NUMERIC NOT NULL
            )
        """,
        "columns": ["order_item_id", "order_id", "product_id", "quantity", "unit_price", "discount_amount"],
        "types": [int, int, int, int, float, float],
    },
    "payments": {
        "ddl": """
            CREATE TABLE raw.payments (
                payment_id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES raw.orders(order_id),
                payment_method TEXT NOT NULL,
                card_last4 TEXT,
                amount NUMERIC NOT NULL,
                payment_status TEXT NOT NULL,
                paid_at TIMESTAMP NOT NULL
            )
        """,
        "columns": ["payment_id", "order_id", "payment_method", "card_last4", "amount", "payment_status", "paid_at"],
        "types": [int, int, str, str, float, str, datetime],
    },
    "returns": {
        "ddl": """
            CREATE TABLE raw.returns (
                return_id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES raw.orders(order_id),
                order_item_id INTEGER NOT NULL REFERENCES raw.order_items(order_item_id),
                return_reason TEXT NOT NULL,
                refund_amount NUMERIC NOT NULL,
                returned_at TIMESTAMP NOT NULL
            )
        """,
        "columns": ["return_id", "order_id", "order_item_id", "return_reason", "refund_amount", "returned_at"],
        "types": [int, int, int, str, float, datetime],
    },
}

# Load order respects FK dependencies between raw tables.
RAW_LOAD_ORDER = ["marketing_campaigns", "customers", "products", "orders", "order_items", "payments", "returns"]


def _cast(value: str, py_type):
    if value in ("", None):
        return None
    if py_type is bool:
        return value.strip().lower() == "true"
    if py_type is int:
        return int(value)
    if py_type is float:
        return float(value)
    if py_type is date:
        return datetime.strptime(value, "%Y-%m-%d").date()
    if py_type is datetime:
        return datetime.strptime(value, "%Y-%m-%d")
    return value


def load_raw_schema() -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS raw CASCADE"))
        conn.execute(text("CREATE SCHEMA raw"))
        for table_name in RAW_LOAD_ORDER:
            conn.execute(text(RAW_TABLES[table_name]["ddl"]))

    for table_name in RAW_LOAD_ORDER:
        spec = RAW_TABLES[table_name]
        csv_path = RAW_DIR / f"{table_name}.csv"
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                {col: _cast(row[col], py_type) for col, py_type in zip(spec["columns"], spec["types"])}
                for row in reader
            ]
        if not rows:
            continue
        columns = spec["columns"]
        placeholders = ", ".join(f":{c}" for c in columns)
        stmt = text(f"INSERT INTO raw.{table_name} ({', '.join(columns)}) VALUES ({placeholders})")
        with engine.begin() as conn:
            conn.execute(stmt, rows)
        print(f"  raw.{table_name}: {len(rows)} rows")


# ---------------------------------------------------------------------------
# Catalog: ContextIQ's own metadata about the raw data
# ---------------------------------------------------------------------------

def _parse_dt(value):
    """YAML's implicit timestamp resolver usually turns ISO-looking
    strings into datetimes already, but fall back to explicit parsing so
    this doesn't silently break if a value isn't auto-resolved."""
    if value is None or isinstance(value, (datetime, date)):
        return value
    return datetime.fromisoformat(str(value))


def clear_catalog(session) -> None:
    for model in [DataQualityCheck, Documentation, LineageEdge]:
        session.query(model).delete()
    session.execute(text("DELETE FROM asset_tags"))
    session.query(DatasetColumn).delete()
    session.query(Asset).delete()
    session.query(BusinessTerm).delete()
    session.query(Tag).delete()
    session.query(Owner).delete()
    session.commit()


def get_or_create_owner(session, owners: dict, spec: dict) -> Owner:
    key = spec["name"]
    if key not in owners:
        owner = Owner(name=spec["name"], email=spec.get("email"), team=spec.get("team"))
        session.add(owner)
        session.flush()
        owners[key] = owner
    return owners[key]


def get_or_create_tag(session, tags: dict, name: str) -> Tag:
    if name not in tags:
        tag = Tag(name=name)
        session.add(tag)
        session.flush()
        tags[name] = tag
    return tags[name]


def load_business_terms(session) -> dict:
    data = yaml.safe_load((METADATA_DIR / "business_terms.yaml").read_text(encoding="utf-8"))
    terms = {}
    for entry in data["terms"]:
        term = BusinessTerm(
            term=entry["term"],
            definition=entry["definition"].strip(),
            domain=entry.get("domain"),
        )
        session.add(term)
        session.flush()
        terms[term.term] = term
    return terms


def load_assets(session, business_terms: dict) -> dict:
    assets: dict = {}
    owners: dict = {}
    tags: dict = {}

    asset_files = sorted(p for p in METADATA_DIR.glob("*.yaml") if p.name != "business_terms.yaml")
    for path in asset_files:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))

        owner = get_or_create_owner(session, owners, spec["owner"]) if spec.get("owner") else None
        asset_tag_objs = [get_or_create_tag(session, tags, name) for name in spec.get("tags", [])]

        asset = Asset(
            asset_id=spec["asset_id"],
            asset_name=spec["asset_name"],
            asset_type=AssetType(spec["asset_type"]),
            description=(spec.get("description") or "").strip() or None,
            domain=spec.get("domain"),
            source_system=spec.get("source_system"),
            owner=owner,
            pii_status=PIIStatus(spec.get("pii_status", "unknown")),
            quality_score=spec.get("quality_score"),
            data_last_updated=_parse_dt(spec.get("data_last_updated")),
            tags=asset_tag_objs,
        )
        session.add(asset)
        session.flush()

        for col in spec.get("columns") or []:
            business_term = business_terms.get(col["business_term"]) if col.get("business_term") else None
            session.add(DatasetColumn(
                asset_id=asset.asset_id,
                column_name=col["name"],
                data_type=col["data_type"],
                description=(col.get("description") or "").strip() or None,
                is_nullable=col.get("is_nullable", True),
                is_pii=col.get("is_pii", False),
                pii_category=col.get("pii_category"),
                business_term=business_term,
            ))

        for check in spec.get("quality_checks") or []:
            session.add(DataQualityCheck(
                asset_id=asset.asset_id,
                check_name=check["check_name"],
                status=QualityCheckStatus(check["status"]),
                score=check.get("score"),
                message=(check.get("message") or "").strip() or None,
                checked_at=_parse_dt(check.get("checked_at")),
            ))

        assets[asset.asset_id] = asset

    session.flush()
    return assets


def load_lineage(session, assets: dict) -> int:
    data = yaml.safe_load(LINEAGE_FILE.read_text(encoding="utf-8"))
    count = 0
    for edge in data["edges"]:
        session.add(LineageEdge(
            source_asset_id=assets[edge["source"]].asset_id,
            target_asset_id=assets[edge["target"]].asset_id,
            transformation=edge.get("transformation"),
            description=(edge.get("description") or "").strip() or None,
        ))
        count += 1
    return count


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def load_documentation(session) -> int:
    count = 0
    for path in sorted(DOCS_DIR.glob("*.md")):
        raw_text = path.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(raw_text)
        if not match:
            raise ValueError(f"{path} is missing YAML frontmatter (expected --- ... --- at the top)")
        front = yaml.safe_load(match.group(1)) or {}
        body = match.group(2).strip()
        session.add(Documentation(
            asset_id=front.get("asset_id") or None,
            title=front["title"],
            content=body,
            doc_type=front["doc_type"],
            source_url=front.get("source_url"),
        ))
        count += 1
    return count


def main() -> None:
    print("Ensuring catalog tables exist...")
    Base.metadata.create_all(bind=engine)

    print("Loading raw schema (the pretend operational warehouse)...")
    load_raw_schema()

    session = SessionLocal()
    try:
        print("Clearing existing catalog rows...")
        clear_catalog(session)

        print("Loading business terms...")
        business_terms = load_business_terms(session)

        print("Loading assets, columns, and quality checks...")
        assets = load_assets(session, business_terms)

        print("Loading lineage edges...")
        edge_count = load_lineage(session, assets)

        print("Loading documentation...")
        doc_count = load_documentation(session)

        session.commit()

        print(
            f"Done. {len(assets)} assets, {edge_count} lineage edges, "
            f"{doc_count} documentation entries, {len(business_terms)} business terms."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
