import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LineageGraph } from "./LineageGraph";

// Deliberately NOT 10 nodes / 8 edges (the current seed data's shape) --
// proves the component renders whatever it's given, not a hardcoded count.
const nodes = [
  { asset_id: "a", asset_name: "Asset A", asset_type: "table" as const, pii_status: "none" as const },
  { asset_id: "b", asset_name: "Asset B", asset_type: "model" as const, pii_status: "contains_pii" as const },
  { asset_id: "c", asset_name: "Asset C", asset_type: "dashboard" as const, pii_status: "unknown" as const },
];
const edges = [
  { source_asset_id: "a", target_asset_id: "b", transformation: "join", description: "a feeds b" },
  { source_asset_id: "b", target_asset_id: "c", transformation: "aggregate", description: "b feeds c" },
];

// NOTE on scope: this verifies node rendering, content, and click
// wiring -- the parts jsdom can actually exercise. It does NOT assert on
// `.react-flow__edge` SVG path elements: @xyflow/react's edge-path
// computation depends on real CSS layout (getComputedStyle/DOMMatrix
// transforms resolved by an actual browser layout engine) that jsdom does
// not provide, even for React Flow's own *default*, uncustomized node
// type with no app code involved -- confirmed by isolated testing during
// this feature's implementation. The edge-CONSTRUCTION logic (which
// asset connects to which, in which direction) is what actually carries
// business meaning, and is covered exhaustively, independent of
// rendering, in hopsToGraph.test.ts. The full-graph endpoint's edge data
// (source/target pairs, count) is verified against the live database in
// backend/tests/test_api_lineage.py.
describe("LineageGraph", () => {
  it("renders every given node with its name and badges", async () => {
    render(<LineageGraph nodes={nodes} edges={edges} />);

    await waitFor(() => {
      expect(document.querySelectorAll(".react-flow__node")).toHaveLength(3);
    });

    expect(screen.getByText("Asset A")).toBeInTheDocument();
    expect(screen.getByText("Asset B")).toBeInTheDocument();
    expect(screen.getByText("Asset C")).toBeInTheDocument();
    expect(screen.getByText("Contains PII")).toBeInTheDocument();
  });

  it("calls onNodeClick with the asset id when a node is clicked", async () => {
    const onNodeClick = vi.fn();
    render(<LineageGraph nodes={nodes} edges={edges} onNodeClick={onNodeClick} />);

    await waitFor(() => {
      expect(document.querySelectorAll(".react-flow__node")).toHaveLength(3);
    });

    const nodeEl = document.querySelector('[data-id="a"]') as HTMLElement;
    nodeEl.click();

    expect(onNodeClick).toHaveBeenCalledWith("a");
  });

  it("renders nothing extra for an empty graph", () => {
    render(<LineageGraph nodes={[]} edges={[]} />);
    expect(document.querySelectorAll(".react-flow__node")).toHaveLength(0);
  });
});
