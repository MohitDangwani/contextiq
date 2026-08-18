import { Link } from "react-router-dom";

import { CollapsibleSection } from "../common/CollapsibleSection";
import { EvidencePanel } from "./EvidencePanel";
import { ToolTracePanel } from "./ToolTracePanel";
import type { ChatResponse } from "../../types/api";

interface GroundedAnswerCardProps {
  response: ChatResponse & { grounding_status: "supported" | "partial" };
}

export function GroundedAnswerCard({ response }: GroundedAnswerCardProps) {
  const isPartial = response.grounding_status === "partial";

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <span
          className={
            isPartial
              ? "rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700"
              : "rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700"
          }
        >
          {isPartial ? "Answered from partial evidence" : "Grounded in ContextIQ evidence"}
        </span>
      </div>

      <p className="mt-3 whitespace-pre-wrap text-sm text-slate-800">{response.answer}</p>

      {response.sources.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {response.sources.map((source, i) =>
            source.asset_id ? (
              <Link
                key={`${source.label}-${i}`}
                to={`/assets/${encodeURIComponent(source.asset_id)}`}
                className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
              >
                {source.label}
              </Link>
            ) : (
              <span
                key={`${source.label}-${i}`}
                className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs font-medium text-slate-600"
              >
                {source.label}
              </span>
            ),
          )}
        </div>
      )}

      <div className="mt-3 space-y-1">
        <CollapsibleSection title="Evidence">
          <EvidencePanel evidence={response.evidence} />
        </CollapsibleSection>
        <CollapsibleSection title="Agent Activity">
          <ToolTracePanel trace={response.trace} />
        </CollapsibleSection>
      </div>
    </div>
  );
}
