import type { AssetLineage } from "../../types/api";
import type { GraphEdgeInput, GraphNodeInput } from "./types";

// Pure shape-adapter: turns the per-asset traversal response
// (asset_id + upstream/downstream hops, from GET /api/assets/{id}/lineage)
// into the same {nodes, edges} shape the whole-catalog view already uses --
// NOT a re-traversal, just reshaping data the backend already computed.
// Edge direction matches the same convention app/agent/tools.py's
// citations use: upstream hop asset_id -> via_asset_id (flows toward the
// center asset), via_asset_id -> downstream hop asset_id (flows away from it).
export function hopsToGraph(lineage: AssetLineage, centerAssetName: string): { nodes: GraphNodeInput[]; edges: GraphEdgeInput[] } {
  const nodesById = new Map<string, GraphNodeInput>();
  nodesById.set(lineage.asset_id, { asset_id: lineage.asset_id, asset_name: centerAssetName });

  const edges: GraphEdgeInput[] = [];

  for (const hop of lineage.upstream) {
    nodesById.set(hop.asset_id, { asset_id: hop.asset_id, asset_name: hop.asset_name });
    edges.push({
      source_asset_id: hop.asset_id,
      target_asset_id: hop.via_asset_id,
      transformation: hop.transformation,
      description: hop.description,
    });
  }

  for (const hop of lineage.downstream) {
    nodesById.set(hop.asset_id, { asset_id: hop.asset_id, asset_name: hop.asset_name });
    edges.push({
      source_asset_id: hop.via_asset_id,
      target_asset_id: hop.asset_id,
      transformation: hop.transformation,
      description: hop.description,
    });
  }

  return { nodes: [...nodesById.values()], edges };
}
