import { get } from "./httpClient";
import type { SearchResults } from "../types/api";

export function federatedSearch(q: string): Promise<SearchResults> {
  return get<SearchResults>(`/search?q=${encodeURIComponent(q)}`);
}
