import type { PIIStatus } from "../../types/api";

const STYLES: Record<PIIStatus, string> = {
  contains_pii: "bg-rose-50 text-rose-700 border-rose-200",
  none: "bg-emerald-50 text-emerald-700 border-emerald-200",
  unknown: "bg-slate-100 text-slate-500 border-slate-200",
};

const LABELS: Record<PIIStatus, string> = {
  contains_pii: "Contains PII",
  none: "No PII",
  unknown: "PII unknown",
};

export function PIIBadge({ status }: { status: PIIStatus }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  );
}
