import { Handle, Position, type NodeProps } from "@xyflow/react";

import { AssetTypeBadge } from "../catalog/AssetTypeBadge";
import { PIIBadge } from "../catalog/PIIBadge";
import type { AssetType, PIIStatus } from "../../types/api";

export interface AssetNodeData {
  assetName: string;
  // Only the whole-catalog graph (backed by /api/lineage/graph) has these;
  // the focused per-asset view (backed by /api/assets/{id}/lineage) only
  // has hop names -- badges are simply omitted when absent, not faked.
  assetType?: AssetType;
  piiStatus?: PIIStatus;
  isFocus?: boolean;
  [key: string]: unknown;
}

export function AssetNode({ data }: NodeProps) {
  const { assetName, assetType, piiStatus, isFocus } = data as AssetNodeData;

  return (
    <div
      className={`rounded-lg border bg-white px-3 py-2 shadow-sm ${
        isFocus ? "border-indigo-400 ring-2 ring-indigo-100" : "border-slate-200"
      }`}
      style={{ width: 180 }}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-300" />
      <p className="truncate text-xs font-semibold text-slate-800">{assetName}</p>
      <div className="mt-1 flex flex-wrap gap-1">
        {assetType && <AssetTypeBadge type={assetType} />}
        {piiStatus && <PIIBadge status={piiStatus} />}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-slate-300" />
    </div>
  );
}
