"""Lineage traversal: given an asset, find what feeds into it (upstream)
and what it feeds into (downstream), any number of hops away.

Implemented as an in-Python BFS over all lineage_edges fetched once,
rather than a recursive SQL CTE — the catalog is small (a handful of
edges), and a BFS over an edge list is far easier to read and reason
about than a recursive CTE buried in the ORM. Revisit this if the
lineage graph ever grows into the thousands of edges.
"""
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Asset, LineageEdge
from app.models.enums import AssetType, PIIStatus


@dataclass
class LineageHop:
    asset_id: str
    asset_name: str
    depth: int
    transformation: str | None
    description: str | None
    via_asset_id: str  # the specific neighboring node this hop's edge connects
    # to/from -- lets a caller state the edge's exact two endpoints (e.g.
    # "orders -> order_items") instead of just "N hops away via
    # TRANSFORMATION", which is ambiguous once there's more than one hop
    # and leaves room to misattribute a transformation to the wrong edge
    # when narrating a multi-hop chain in prose.


@dataclass
class LineageResult:
    asset_id: str
    upstream: list[LineageHop]
    downstream: list[LineageHop]


def _traverse(
    start: str,
    edges_by_node: dict[str, list[LineageEdge]],
    neighbor_of: Callable[[LineageEdge], str],
    asset_names: dict[str, str],
    max_depth: int,
) -> list[LineageHop]:
    hops: list[LineageHop] = []
    visited = {start}
    queue: list[tuple[str, int]] = [(start, 0)]
    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        for edge in edges_by_node.get(current, []):
            neighbor = neighbor_of(edge)
            if neighbor in visited:
                continue
            visited.add(neighbor)
            hops.append(LineageHop(
                asset_id=neighbor,
                asset_name=asset_names.get(neighbor, neighbor),
                depth=depth + 1,
                transformation=edge.transformation,
                description=edge.description,
                via_asset_id=current,
            ))
            queue.append((neighbor, depth + 1))
    return hops


def get_lineage(
    db: Session, asset_id: str, direction: str = "both", max_depth: int = 10
) -> LineageResult | None:
    if db.get(Asset, asset_id) is None:
        return None

    edges = db.query(LineageEdge).all()
    asset_names = {a.asset_id: a.asset_name for a in db.query(Asset).all()}

    downstream_by_source: dict[str, list[LineageEdge]] = {}
    upstream_by_target: dict[str, list[LineageEdge]] = {}
    for edge in edges:
        downstream_by_source.setdefault(edge.source_asset_id, []).append(edge)
        upstream_by_target.setdefault(edge.target_asset_id, []).append(edge)

    upstream = (
        _traverse(asset_id, upstream_by_target, lambda e: e.source_asset_id, asset_names, max_depth)
        if direction in ("upstream", "both")
        else []
    )
    downstream = (
        _traverse(asset_id, downstream_by_source, lambda e: e.target_asset_id, asset_names, max_depth)
        if direction in ("downstream", "both")
        else []
    )

    return LineageResult(asset_id=asset_id, upstream=upstream, downstream=downstream)


@dataclass
class GraphNode:
    asset_id: str
    asset_name: str
    asset_type: AssetType
    domain: str | None
    pii_status: PIIStatus


@dataclass
class GraphEdge:
    source_asset_id: str
    target_asset_id: str
    transformation: str | None
    description: str | None


@dataclass
class FullGraphResult:
    nodes: list[GraphNode]
    edges: list[GraphEdge]


def get_full_graph(db: Session) -> FullGraphResult:
    """Every asset and every lineage edge in the catalog, as a flat graph --
    for a whole-catalog visualization, not a per-asset traversal. A
    different query shape than get_lineage()'s BFS (here we already have
    all nodes and edges available; there's nothing to traverse), so this
    intentionally does not call _traverse()/get_lineage(). Both still read
    the same Asset/LineageEdge models -- no duplicated data access."""
    assets = db.query(Asset).all()
    edges = db.query(LineageEdge).all()
    return FullGraphResult(
        nodes=[
            GraphNode(
                asset_id=a.asset_id, asset_name=a.asset_name, asset_type=a.asset_type,
                domain=a.domain, pii_status=a.pii_status,
            )
            for a in assets
        ],
        edges=[
            GraphEdge(
                source_asset_id=e.source_asset_id, target_asset_id=e.target_asset_id,
                transformation=e.transformation, description=e.description,
            )
            for e in edges
        ],
    )
