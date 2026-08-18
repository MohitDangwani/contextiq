import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { SearchBar } from "../components/catalog/SearchBar";
import { AssetTable } from "../components/catalog/AssetTable";
import { LoadingState } from "../components/common/LoadingState";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { listAssets } from "../services/assetsService";
import type { AssetType } from "../types/api";

const ASSET_TYPES: AssetType[] = ["table", "view", "dashboard", "model"];

export function CatalogPage() {
  const [q, setQ] = useState("");
  const [domain, setDomain] = useState("");
  const [assetType, setAssetType] = useState("");
  const [piiOnly, setPiiOnly] = useState(false);

  // Unfiltered baseline, used only to populate the domain dropdown with
  // whatever domains actually exist in the live catalog -- never a fixed list.
  const allAssetsQuery = useQuery({ queryKey: ["assets", "all"], queryFn: () => listAssets() });
  const domains = useMemo(() => {
    const set = new Set((allAssetsQuery.data ?? []).map((a) => a.domain).filter((d): d is string => Boolean(d)));
    return [...set].sort();
  }, [allAssetsQuery.data]);

  const assetsQuery = useQuery({
    queryKey: ["assets", { q, domain, assetType, piiOnly }],
    queryFn: () => listAssets({ q: q || undefined, domain: domain || undefined, asset_type: assetType || undefined, pii_only: piiOnly }),
  });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Data Catalog</h1>
        <p className="mt-1 text-sm text-slate-500">Browse every asset ContextIQ knows about, with ownership, PII, and quality at a glance.</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-64 flex-1">
          <SearchBar value={q} onChange={setQ} placeholder="Search assets by name or description…" />
        </div>
        <select
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm"
        >
          <option value="">All domains</option>
          {domains.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <select
          value={assetType}
          onChange={(e) => setAssetType(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm"
        >
          <option value="">All types</option>
          {ASSET_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-sm text-slate-600">
          <input type="checkbox" checked={piiOnly} onChange={(e) => setPiiOnly(e.target.checked)} />
          PII only
        </label>
      </div>

      {assetsQuery.isPending && <LoadingState label="Loading assets…" />}
      {assetsQuery.isError && <ErrorState message="Could not load the asset catalog." onRetry={() => assetsQuery.refetch()} />}
      {assetsQuery.isSuccess && assetsQuery.data.length === 0 && (
        <EmptyState message="No assets match your filters" hint="Try clearing a filter or search term." />
      )}
      {assetsQuery.isSuccess && assetsQuery.data.length > 0 && <AssetTable assets={assetsQuery.data} />}
    </div>
  );
}
