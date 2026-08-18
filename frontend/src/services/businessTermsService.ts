import { get } from "./httpClient";
import type { BusinessTerm } from "../types/api";

export function searchTerms(q: string): Promise<BusinessTerm[]> {
  return get<BusinessTerm[]>(`/business-terms?q=${encodeURIComponent(q)}`);
}

export function getTerm(term: string): Promise<BusinessTerm> {
  return get<BusinessTerm>(`/business-terms/${encodeURIComponent(term)}`);
}
