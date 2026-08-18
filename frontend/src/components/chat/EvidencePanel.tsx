import type { EvidenceItem } from "../../types/api";

interface EvidencePanelProps {
  evidence: EvidenceItem[];
}

export function EvidencePanel({ evidence }: EvidencePanelProps) {
  if (evidence.length === 0) {
    return <p className="text-xs text-slate-400">No evidence was retrieved for this answer.</p>;
  }

  return (
    <ul className="space-y-2">
      {evidence.map((item, i) => (
        <li key={`${item.source_type}-${item.citation}-${i}`} className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <p>{item.detail}</p>
          <p className="mt-1 font-mono text-[11px] text-slate-400">{item.citation}</p>
        </li>
      ))}
    </ul>
  );
}
