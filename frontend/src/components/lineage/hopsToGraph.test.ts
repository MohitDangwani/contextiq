import { describe, expect, it } from "vitest";

import { hopsToGraph } from "./hopsToGraph";
import type { AssetLineage } from "../../types/api";

describe("hopsToGraph", () => {
  it("includes the center asset plus every hop, deduplicated, as nodes", () => {
    const lineage: AssetLineage = {
      asset_id: "orders",
      upstream: [
        { asset_id: "customers", asset_name: "Customers", depth: 1, transformation: "fk", description: null, via_asset_id: "orders" },
      ],
      downstream: [
        { asset_id: "order_items", asset_name: "Order Items", depth: 1, transformation: "fk", description: null, via_asset_id: "orders" },
      ],
    };

    const { nodes } = hopsToGraph(lineage, "Orders");

    expect(nodes.map((n) => n.asset_id).sort()).toEqual(["customers", "order_items", "orders"]);
    expect(nodes.find((n) => n.asset_id === "orders")?.asset_name).toBe("Orders");
  });

  it("orients upstream edges toward the via_asset_id (flowing into the center)", () => {
    const lineage: AssetLineage = {
      asset_id: "orders",
      upstream: [
        { asset_id: "customers", asset_name: "Customers", depth: 1, transformation: "fk", description: "d", via_asset_id: "orders" },
      ],
      downstream: [],
    };

    const { edges } = hopsToGraph(lineage, "Orders");

    expect(edges).toEqual([
      { source_asset_id: "customers", target_asset_id: "orders", transformation: "fk", description: "d" },
    ]);
  });

  it("orients downstream edges away from the via_asset_id (flowing out of the center)", () => {
    const lineage: AssetLineage = {
      asset_id: "orders",
      upstream: [],
      downstream: [
        { asset_id: "order_items", asset_name: "Order Items", depth: 1, transformation: "fk", description: "d", via_asset_id: "orders" },
      ],
    };

    const { edges } = hopsToGraph(lineage, "Orders");

    expect(edges).toEqual([
      { source_asset_id: "orders", target_asset_id: "order_items", transformation: "fk", description: "d" },
    ]);
  });

  it("handles a multi-hop chain, using each hop's own via_asset_id rather than the center", () => {
    // customers -> orders -> order_items, queried from "orders": one direct
    // upstream hop (customers, via orders) plus a 2-hop downstream hop
    // (order_items is direct; this checks the shape generalizes, not a
    // specific hardcoded catalog).
    const lineage: AssetLineage = {
      asset_id: "orders",
      upstream: [
        { asset_id: "customers", asset_name: "Customers", depth: 1, transformation: "fk1", description: null, via_asset_id: "orders" },
      ],
      downstream: [
        { asset_id: "order_items", asset_name: "Order Items", depth: 1, transformation: "fk2", description: null, via_asset_id: "orders" },
        { asset_id: "revenue_model", asset_name: "Revenue Model", depth: 2, transformation: "dbt", description: null, via_asset_id: "order_items" },
      ],
    };

    const { edges } = hopsToGraph(lineage, "Orders");

    expect(edges).toEqual([
      { source_asset_id: "customers", target_asset_id: "orders", transformation: "fk1", description: null },
      { source_asset_id: "orders", target_asset_id: "order_items", transformation: "fk2", description: null },
      { source_asset_id: "order_items", target_asset_id: "revenue_model", transformation: "dbt", description: null },
    ]);
  });

  it("produces an empty graph shape (except the center node) when there is no lineage", () => {
    const lineage: AssetLineage = { asset_id: "standalone_asset", upstream: [], downstream: [] };

    const { nodes, edges } = hopsToGraph(lineage, "Standalone Asset");

    expect(nodes).toEqual([{ asset_id: "standalone_asset", asset_name: "Standalone Asset" }]);
    expect(edges).toEqual([]);
  });
});
