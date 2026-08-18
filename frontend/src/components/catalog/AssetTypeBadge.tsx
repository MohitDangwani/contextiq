import type { AssetType } from "../../types/api";

const STYLES: Record<AssetType, string> = {
  table: "bg-sky-50 text-sky-700 border-sky-200",
  view: "bg-violet-50 text-violet-700 border-violet-200",
  dashboard: "bg-orange-50 text-orange-700 border-orange-200",
  model: "bg-teal-50 text-teal-700 border-teal-200",
};

export function AssetTypeBadge({ type }: { type: AssetType }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${STYLES[type]}`}>
      {type}
    </span>
  );
}
