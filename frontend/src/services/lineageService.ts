import { get } from "./httpClient";
import type { LineageGraph } from "../types/api";

export function getFullGraph(): Promise<LineageGraph> {
  return get<LineageGraph>("/lineage/graph");
}
