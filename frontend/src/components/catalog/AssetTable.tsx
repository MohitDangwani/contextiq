import { Link } from "react-router-dom";

import { AssetTypeBadge } from "./AssetTypeBadge";
import { PIIBadge } from "./PIIBadge";
import { QualityBadge } from "./QualityBadge";
import type { AssetSummary } from "../../types/api";

interface AssetTableProps {
  assets: AssetSummary[];
}

export function AssetTable({ assets }: AssetTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-4 py-2 font-medium">Asset</th>
            <th className="px-4 py-2 font-medium">Type</th>
            <th className="px-4 py-2 font-medium">Domain</th>
            <th className="px-4 py-2 font-medium">PII</th>
            <th className="px-4 py-2 font-medium">Quality</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {assets.map((asset) => (
            <tr key={asset.asset_id} className="hover:bg-slate-50">
              <td className="px-4 py-2.5">
                <Link to={`/assets/${encodeURIComponent(asset.asset_id)}`} className="font-medium text-indigo-700 hover:underline">
                  {asset.asset_name}
                </Link>
              </td>
              <td className="px-4 py-2.5">
                <AssetTypeBadge type={asset.asset_type} />
              </td>
              <td className="px-4 py-2.5 text-slate-600">{asset.domain ?? "—"}</td>
              <td className="px-4 py-2.5">
                <PIIBadge status={asset.pii_status} />
              </td>
              <td className="px-4 py-2.5">
                <QualityBadge score={asset.quality_score} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
