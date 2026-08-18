import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { AssetTypeBadge } from "../components/catalog/AssetTypeBadge";
import { PIIBadge } from "../components/catalog/PIIBadge";
import { QualityBadge } from "../components/catalog/QualityBadge";
import { LoadingState } from "../components/common/LoadingState";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { LineageGraph } from "../components/lineage/LineageGraph";
import { hopsToGraph } from "../components/lineage/hopsToGraph";
import { getAsset, getAssetLineage, getDocumentation, getQuality, getSchema } from "../services/assetsService";

export function AssetDetailPage() {
  const { assetId } = useParams<{ assetId: string }>();
  const navigate = useNavigate();
  const id = assetId ?? "";

  const assetQuery = useQuery({ queryKey: ["asset", id], queryFn: () => getAsset(id), enabled: !!id });
  const schemaQuery = useQuery({ queryKey: ["asset", id, "schema"], queryFn: () => getSchema(id), enabled: !!id });
  const qualityQuery = useQuery({ queryKey: ["asset", id, "quality"], queryFn: () => getQuality(id), enabled: !!id });
  const docsQuery = useQuery({ queryKey: ["asset", id, "documentation"], queryFn: () => getDocumentation(id), enabled: !!id });
  const lineageQuery = useQuery({ queryKey: ["asset", id, "lineage"], queryFn: () => getAssetLineage(id), enabled: !!id });

  if (assetQuery.isPending) return <LoadingState label="Loading asset…" />;
  if (assetQuery.isError) return <ErrorState message={`Could not load asset "${id}".`} onRetry={() => assetQuery.refetch()} />;

  const asset = assetQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold text-slate-900">{asset.asset_name}</h1>
          <AssetTypeBadge type={asset.asset_type} />
          <PIIBadge status={asset.pii_status} />
          <QualityBadge score={asset.quality_score} />
        </div>
        <p className="mt-1 font-mono text-xs text-slate-400">{asset.asset_id}</p>
        {asset.description && <p className="mt-2 text-sm text-slate-600">{asset.description}</p>}
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-700">Metadata</h2>
        <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
          <dt className="text-slate-400">Domain</dt>
          <dd className="text-slate-700">{asset.domain ?? "—"}</dd>
          <dt className="text-slate-400">Source system</dt>
          <dd className="text-slate-700">{asset.source_system ?? "—"}</dd>
          <dt className="text-slate-400">Owner</dt>
          <dd className="text-slate-700">{asset.owner ? `${asset.owner.name}${asset.owner.team ? ` (${asset.owner.team})` : ""}` : "—"}</dd>
          <dt className="text-slate-400">Last updated</dt>
          <dd className="text-slate-700">{asset.data_last_updated ? new Date(asset.data_last_updated).toLocaleString() : "—"}</dd>
        </dl>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-700">Schema</h2>
        {schemaQuery.isPending && <LoadingState label="Loading schema…" />}
        {schemaQuery.isError && <ErrorState message="Could not load schema." onRetry={() => schemaQuery.refetch()} />}
        {schemaQuery.isSuccess && schemaQuery.data.length === 0 && <EmptyState message="No columns recorded for this asset." />}
        {schemaQuery.isSuccess && schemaQuery.data.length > 0 && (
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-400">
                <tr>
                  <th className="py-1 pr-4 font-medium">Column</th>
                  <th className="py-1 pr-4 font-medium">Type</th>
                  <th className="py-1 pr-4 font-medium">PII</th>
                  <th className="py-1 font-medium">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {schemaQuery.data.map((col) => (
                  <tr key={col.column_name}>
                    <td className="py-1.5 pr-4 font-mono text-xs text-slate-700">{col.column_name}</td>
                    <td className="py-1.5 pr-4 text-slate-500">{col.data_type}</td>
                    <td className="py-1.5 pr-4">{col.is_pii ? <span className="text-rose-600">Yes{col.pii_category ? ` (${col.pii_category})` : ""}</span> : <span className="text-slate-400">No</span>}</td>
                    <td className="py-1.5 text-slate-600">{col.description ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-700">Quality</h2>
        {qualityQuery.isPending && <LoadingState label="Loading quality checks…" />}
        {qualityQuery.isError && <ErrorState message="Could not load quality checks." onRetry={() => qualityQuery.refetch()} />}
        {qualityQuery.isSuccess && qualityQuery.data.checks.length === 0 && <EmptyState message="No quality checks recorded for this asset." />}
        {qualityQuery.isSuccess && qualityQuery.data.checks.length > 0 && (
          <ul className="mt-2 space-y-1.5">
            {qualityQuery.data.checks.map((check) => (
              <li key={check.check_name} className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-1.5 text-sm">
                <span className="text-slate-700">{check.check_name}</span>
                <span
                  className={
                    check.status === "pass"
                      ? "text-emerald-600"
                      : check.status === "warn"
                        ? "text-amber-600"
                        : "text-rose-600"
                  }
                >
                  {check.status}
                  {check.message ? ` — ${check.message}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-700">Documentation</h2>
        {docsQuery.isPending && <LoadingState label="Loading documentation…" />}
        {docsQuery.isError && <ErrorState message="Could not load documentation." onRetry={() => docsQuery.refetch()} />}
        {docsQuery.isSuccess && docsQuery.data.length === 0 && <EmptyState message="No documentation recorded for this asset." />}
        {docsQuery.isSuccess && docsQuery.data.length > 0 && (
          <ul className="mt-2 space-y-2">
            {docsQuery.data.map((doc) => (
              <li key={doc.id} className="rounded-md bg-slate-50 px-3 py-2 text-sm">
                <p className="font-medium text-slate-700">{doc.title}</p>
                <p className="mt-0.5 text-slate-600">{doc.content}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section id="lineage" className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-700">Lineage</h2>
        {lineageQuery.isPending && <LoadingState label="Loading lineage…" />}
        {lineageQuery.isError && <ErrorState message="Could not load lineage." onRetry={() => lineageQuery.refetch()} />}
        {lineageQuery.isSuccess && lineageQuery.data.upstream.length === 0 && lineageQuery.data.downstream.length === 0 && (
          <EmptyState message="No lineage relationships recorded for this asset." />
        )}
        {lineageQuery.isSuccess &&
          (lineageQuery.data.upstream.length > 0 || lineageQuery.data.downstream.length > 0) &&
          (() => {
            const { nodes, edges } = hopsToGraph(lineageQuery.data, asset.asset_name);
            return (
              <div className="mt-2">
                <LineageGraph
                  nodes={nodes}
                  edges={edges}
                  focusAssetId={asset.asset_id}
                  onNodeClick={(clickedId) => navigate(`/assets/${encodeURIComponent(clickedId)}`)}
                  height={300}
                />
              </div>
            );
          })()}
      </section>
    </div>
  );
}
