import dagre from "dagre";
import type { Node } from "@xyflow/react";

const NODE_WIDTH = 180;
const NODE_HEIGHT = 60;

// Positions an arbitrary set of nodes/edges left-to-right -- count-agnostic,
// works the same whether given 3 nodes or 300.
export function layoutNodes(nodes: Node[], edges: { source: string; target: string }[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 32, ranksep: 90 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  return nodes.map((node) => {
    const { x, y } = g.node(node.id);
    return { ...node, position: { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 } };
  });
}

export const LINEAGE_NODE_WIDTH = NODE_WIDTH;
export const LINEAGE_NODE_HEIGHT = NODE_HEIGHT;
