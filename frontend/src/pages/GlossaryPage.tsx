import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { SearchBar } from "../components/catalog/SearchBar";
import { LoadingState } from "../components/common/LoadingState";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { searchTerms } from "../services/businessTermsService";

export function GlossaryPage() {
  const [q, setQ] = useState("");

  // GET /api/business-terms requires a non-empty q (min_length=1) -- this
  // is search-first by design, not a workaround: there's no "list all
  // terms" endpoint to fall back to.
  const termsQuery = useQuery({
    queryKey: ["business-terms", q],
    queryFn: () => searchTerms(q),
    enabled: q.trim().length > 0,
  });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Business Glossary</h1>
        <p className="mt-1 text-sm text-slate-500">Search ContextIQ&apos;s business term definitions.</p>
      </div>

      <SearchBar value={q} onChange={setQ} placeholder="Search business terms (e.g. &quot;revenue&quot;)…" />

      {q.trim().length === 0 && <EmptyState message="Search for a business term to get started" />}
      {termsQuery.isPending && q.trim().length > 0 && <LoadingState label="Searching…" />}
      {termsQuery.isError && <ErrorState message="Could not search business terms." onRetry={() => termsQuery.refetch()} />}
      {termsQuery.isSuccess && termsQuery.data.length === 0 && (
        <EmptyState message="No matching business terms" hint="Try a different search term." />
      )}
      {termsQuery.isSuccess && termsQuery.data.length > 0 && (
        <ul className="flex flex-col gap-2">
          {termsQuery.data.map((term) => (
            <li key={term.term} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-800">{term.term}</span>
                {term.domain && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{term.domain}</span>}
              </div>
              <p className="mt-1 text-sm text-slate-600">{term.definition}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
