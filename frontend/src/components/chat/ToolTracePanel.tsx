import type { ToolInvocation } from "../../types/api";

interface ToolTracePanelProps {
  trace: ToolInvocation[];
}

// "Agent Activity" -- observable tool execution only: which tools ran,
// with what (sanitized, already-public catalog-query) arguments, whether
// each call found anything, and a short summary of what it returned.
// This NEVER renders the model's hidden reasoning/chain-of-thought
// (<think>, reasoning_content) -- the backend's ChatResponseOut doesn't
// even carry that field, so there is nothing here to leak. This is a log
// of actions taken, not a transcript of how the model "thought".
export function ToolTracePanel({ trace }: ToolTracePanelProps) {
  if (trace.length === 0) {
    return <p className="text-xs text-slate-400">No tools were called for this question.</p>;
  }

  return (
    <ul className="space-y-2">
      {trace.map((call, i) => (
        <li key={`${call.tool}-${call.timestamp}-${i}`} className="rounded-md border border-slate-100 px-3 py-2 text-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono font-semibold text-slate-700">{call.tool}</span>
            <span
              className={
                call.evidence_count > 0
                  ? "rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700"
                  : "rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500"
              }
            >
              {call.evidence_count > 0 ? `Found ${call.evidence_count} result(s)` : "No results"}
            </span>
          </div>
          <p className="mt-1 font-mono text-[11px] text-slate-400">{JSON.stringify(call.input)}</p>
          <p className="mt-1 text-slate-600">{call.output_summary}</p>
          {call.timestamp && <p className="mt-1 text-[11px] text-slate-300">{call.timestamp}</p>}
        </li>
      ))}
    </ul>
  );
}
