import { get } from "./httpClient";
import type {
  AssetDetail,
  AssetLineage,
  AssetSummary,
  Column,
  Documentation,
  Owner,
  QualityReport,
} from "../types/api";

export interface AssetFilters {
  q?: string;
  domain?: string;
  asset_type?: string;
  tag?: string;
  pii_only?: boolean;
}

function toQuery<T extends object>(params: T): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params) as [string, string | boolean | undefined][]) {
    if (value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export function listAssets(filters: AssetFilters = {}): Promise<AssetSummary[]> {
  return get<AssetSummary[]>(`/assets${toQuery(filters)}`);
}

export function getAsset(assetId: string): Promise<AssetDetail> {
  return get<AssetDetail>(`/assets/${encodeURIComponent(assetId)}`);
}

export function getSchema(assetId: string): Promise<Column[]> {
  return get<Column[]>(`/assets/${encodeURIComponent(assetId)}/schema`);
}

export function getOwner(assetId: string): Promise<Owner> {
  return get<Owner>(`/assets/${encodeURIComponent(assetId)}/owner`);
}

export function getQuality(assetId: string): Promise<QualityReport> {
  return get<QualityReport>(`/assets/${encodeURIComponent(assetId)}/quality`);
}

export function getDocumentation(assetId: string): Promise<Documentation[]> {
  return get<Documentation[]>(`/assets/${encodeURIComponent(assetId)}/documentation`);
}

export function getAssetLineage(
  assetId: string,
  direction: "upstream" | "downstream" | "both" = "both",
): Promise<AssetLineage> {
  return get<AssetLineage>(`/assets/${encodeURIComponent(assetId)}/lineage?direction=${direction}`);
}
