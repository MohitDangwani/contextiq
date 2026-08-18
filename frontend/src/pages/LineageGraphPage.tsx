import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { LineageGraph } from "../components/lineage/LineageGraph";
import { LoadingState } from "../components/common/LoadingState";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { getFullGraph } from "../services/lineageService";

export function LineageGraphPage() {
  const navigate = useNavigate();
  const graphQuery = useQuery({ queryKey: ["lineage", "graph"], queryFn: getFullGraph });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Lineage Graph</h1>
        <p className="mt-1 text-sm text-slate-500">
          How data flows across the catalog. Click a node to inspect that asset; click an edge for the
          transformation behind it.
        </p>
      </div>

      {graphQuery.isPending && <LoadingState label="Loading lineage graph…" />}
      {graphQuery.isError && <ErrorState message="Could not load the lineage graph." onRetry={() => graphQuery.refetch()} />}
      {graphQuery.isSuccess && graphQuery.data.edges.length === 0 && (
        <EmptyState message="No lineage relationships recorded" hint="The catalog has assets, but no lineage edges between them yet." />
      )}
      {graphQuery.isSuccess && graphQuery.data.edges.length > 0 && (
        <LineageGraph
          nodes={graphQuery.data.nodes}
          edges={graphQuery.data.edges}
          onNodeClick={(assetId) => navigate(`/assets/${encodeURIComponent(assetId)}`)}
          height={560}
        />
      )}
    </div>
  );
}
