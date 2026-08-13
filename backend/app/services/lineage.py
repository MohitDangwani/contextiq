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


@dataclass
class LineageHop:
    asset_id: str
    asset_name: str
    depth: int
    transformation: str | None
    description: str | None


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
