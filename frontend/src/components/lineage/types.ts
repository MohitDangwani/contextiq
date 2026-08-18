import type { AssetType, PIIStatus } from "../../types/api";

// Shared shape LineageGraph renders, regardless of which endpoint it came
// from -- the whole-catalog graph (/api/lineage/graph) supplies asset_type
// /pii_status, the per-asset hop view (via hopsToGraph.ts) does not.
export interface GraphNodeInput {
  asset_id: string;
  asset_name: string;
  asset_type?: AssetType;
  pii_status?: PIIStatus;
}

export interface GraphEdgeInput {
  source_asset_id: string;
  target_asset_id: string;
  transformation?: string | null;
  description?: string | null;
}
