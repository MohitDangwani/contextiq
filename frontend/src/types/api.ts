// TypeScript mirrors of backend/app/api/schemas.py. Hand-written rather
// than codegen'd -- the API surface is small (6 route files) and stable
// within this batch. Keep field names/shapes in sync with schemas.py by
// hand if either side changes.

export type AssetType = "table" | "view" | "dashboard" | "model";
export type PIIStatus = "none" | "contains_pii" | "unknown";
export type QualityCheckStatus = "pass" | "warn" | "fail";
export type GroundingStatus = "supported" | "partial" | "not_supported";

export interface Owner {
  name: string;
  email: string | null;
  team: string | null;
}

export interface Tag {
  name: string;
}

export interface BusinessTerm {
  term: string;
  definition: string;
  domain: string | null;
}

export interface AssetSummary {
  asset_id: string;
  asset_name: string;
  asset_type: AssetType;
  domain: string | null;
  pii_status: PIIStatus;
  quality_score: number | null;
  tags: Tag[];
}

export interface AssetDetail extends AssetSummary {
  description: string | null;
  source_system: string | null;
  owner: Owner | null;
  data_last_updated: string | null;
}

export interface Column {
  column_name: string;
  data_type: string;
  description: string | null;
  is_nullable: boolean;
  is_pii: boolean;
  pii_category: string | null;
  business_term: BusinessTerm | null;
}

export interface QualityCheck {
  check_name: string;
  status: QualityCheckStatus;
  score: number | null;
  message: string | null;
  checked_at: string;
}

export interface QualityReport {
  asset_id: string;
  quality_score: number | null;
  overall_status: string;
  checks: QualityCheck[];
}

export interface LineageHop {
  asset_id: string;
  asset_name: string;
  depth: number;
  transformation: string | null;
  description: string | null;
  via_asset_id: string;
}

export interface AssetLineage {
  asset_id: string;
  upstream: LineageHop[];
  downstream: LineageHop[];
}

export interface Documentation {
  id: number;
  title: string;
  doc_type: string;
  source_url: string | null;
  asset_id: string | null;
  content: string;
}

export interface SearchResults {
  assets: AssetSummary[];
  business_terms: BusinessTerm[];
  documentation: Documentation[];
}

// --- Chat (Phase 11) ---

export interface SourceRef {
  label: string;
  asset_id: string | null;
  source_type: string;
}

export interface EvidenceItem {
  source_type: string;
  title: string;
  asset_id: string | null;
  detail: string;
  citation: string;
}

export interface ToolInvocation {
  tool: string;
  input: Record<string, unknown>;
  output_summary: string;
  timestamp: string;
  evidence_count: number;
}

export interface ChatResponse {
  question: string;
  answer: string;
  sources: SourceRef[];
  evidence: EvidenceItem[];
  trace: ToolInvocation[];
  grounding_status: GroundingStatus;
}

// --- Lineage graph (Phase 12) ---

export interface LineageGraphNode {
  asset_id: string;
  asset_name: string;
  asset_type: AssetType;
  domain: string | null;
  pii_status: PIIStatus;
}

export interface LineageGraphEdge {
  source_asset_id: string;
  target_asset_id: string;
  transformation: string | null;
  description: string | null;
}

export interface LineageGraph {
  nodes: LineageGraphNode[];
  edges: LineageGraphEdge[];
}
