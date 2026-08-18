import { useMemo, useState } from "react";
import { ReactFlow, Background, Controls, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { AssetNode, type AssetNodeData } from "./AssetNode";
import { layoutNodes, LINEAGE_NODE_HEIGHT, LINEAGE_NODE_WIDTH } from "./lineageLayout";
import type { GraphEdgeInput, GraphNodeInput } from "./types";

const nodeTypes = { asset: AssetNode };

interface LineageGraphProps {
  nodes: GraphNodeInput[];
  edges: GraphEdgeInput[];
  focusAssetId?: string;
  onNodeClick?: (assetId: string) => void;
  height?: number;
}

// One component, two callers: the whole-catalog view (LineageGraphPage,
// nodes/edges straight from GET /api/lineage/graph) and the focused
// per-asset view (AssetDetailPage, via hopsToGraph.ts over GET
// /api/assets/{id}/lineage). Renders whatever it's given -- no assumption
// about node/edge count.
export function LineageGraph({ nodes, edges, focusAssetId, onNodeClick, height = 420 }: LineageGraphProps) {
  const [selectedEdge, setSelectedEdge] = useState<GraphEdgeInput | null>(null);

  const flowNodes = useMemo<Node[]>(() => {
    const rfNodes: Node[] = nodes.map((n) => ({
      id: n.asset_id,
      type: "asset",
      position: { x: 0, y: 0 },
      // Explicit initial size so React Flow can compute edge paths and
      // fitView immediately, instead of waiting on a ResizeObserver pass
      // over each node's DOM element -- which never fires while the tab
      // is backgrounded/not composited (e.g. an unfocused preview pane).
      width: LINEAGE_NODE_WIDTH,
      height: LINEAGE_NODE_HEIGHT,
      measured: { width: LINEAGE_NODE_WIDTH, height: LINEAGE_NODE_HEIGHT },
      data: {
        assetName: n.asset_name,
        assetType: n.asset_type,
        piiStatus: n.pii_status,
        isFocus: n.asset_id === focusAssetId,
      } satisfies AssetNodeData,
    }));
    return layoutNodes(
      rfNodes,
      edges.map((e) => ({ source: e.source_asset_id, target: e.target_asset_id })),
    );
  }, [nodes, edges, focusAssetId]);

  const flowEdges = useMemo<Edge[]>(
    () =>
      edges.map((e, i) => ({
        id: `${e.source_asset_id}-${e.target_asset_id}-${i}`,
        source: e.source_asset_id,
        target: e.target_asset_id,
        animated: false,
        style: { stroke: "#94a3b8" },
        data: { original: e },
      })),
    [edges],
  );

  return (
    <div className="flex flex-col gap-2">
      <div style={{ height }} className="rounded-lg border border-slate-200 bg-slate-50">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => onNodeClick?.(node.id)}
          onEdgeClick={(_, edge) => {
            const original = (edge.data as { original?: GraphEdgeInput } | undefined)?.original;
            setSelectedEdge(original ?? null);
          }}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} color="#e2e8f0" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      {selectedEdge && (
        <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
          <p className="font-mono text-slate-500">
            {selectedEdge.source_asset_id} → {selectedEdge.target_asset_id}
          </p>
          {selectedEdge.transformation && <p className="mt-1 text-slate-700">{selectedEdge.transformation}</p>}
          {selectedEdge.description && <p className="mt-1 text-slate-500">{selectedEdge.description}</p>}
        </div>
      )}
    </div>
  );
}
