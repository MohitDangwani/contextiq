"""Tests for the Phase 12 lineage HTTP endpoints: the new whole-catalog
graph route (GET /api/lineage/graph) and the via_asset_id addition to the
existing per-asset route (GET /api/assets/{id}/lineage).

Fast, DB-only (no LLM) -- uses FastAPI's TestClient against the real,
already-seeded Postgres database, the same "live DB, no mocks" convention
as the rest of this project's tests, just over HTTP instead of calling
Python functions directly (this repo's first FastAPI-route tests, since
no chat/lineage-graph route existed before this phase).

The full-graph assertions are checked against data/lineage/lineage.yaml
directly (the same source of truth scripts/seed_database.py loads from),
not against hardcoded literals -- this is a regression check against
whatever the catalog is currently seeded with, not a business rule the
application itself depends on.
"""
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_LINEAGE_YAML = (
    Path(__file__).resolve().parent.parent.parent / "data" / "lineage" / "lineage.yaml"
)


def _expected_edges() -> set[tuple[str, str]]:
    raw = yaml.safe_load(_LINEAGE_YAML.read_text(encoding="utf-8"))
    return {(e["source"], e["target"]) for e in raw["edges"]}


def test_full_graph_matches_lineage_yaml():
    response = client.get("/api/lineage/graph")
    assert response.status_code == 200
    body = response.json()

    expected_edges = _expected_edges()
    actual_edges = {(e["source_asset_id"], e["target_asset_id"]) for e in body["edges"]}
    assert actual_edges == expected_edges

    expected_asset_ids = {s for pair in expected_edges for s in pair}
    actual_asset_ids = {n["asset_id"] for n in body["nodes"]}
    # Every asset referenced by an edge must appear as a node -- the graph
    # is a flat dump of ALL assets, so this is a subset check, not equality
    # (assets with no lineage edges at all are still valid nodes).
    assert expected_asset_ids <= actual_asset_ids


def test_full_graph_node_shape():
    response = client.get("/api/lineage/graph")
    body = response.json()
    assert body["nodes"], "expected at least one asset in the catalog"
    node = body["nodes"][0]
    assert {"asset_id", "asset_name", "asset_type", "domain", "pii_status"} <= node.keys()


def test_asset_lineage_includes_via_asset_id():
    response = client.get("/api/assets/orders/lineage")
    assert response.status_code == 200
    body = response.json()
    hops = body["upstream"] + body["downstream"]
    assert hops, "expected 'orders' to have at least one lineage hop"
    for hop in hops:
        assert "via_asset_id" in hop
        assert hop["via_asset_id"]


def test_asset_lineage_unknown_asset_404():
    response = client.get("/api/assets/does_not_exist/lineage")
    assert response.status_code == 404
