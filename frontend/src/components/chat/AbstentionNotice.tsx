import { CollapsibleSection } from "../common/CollapsibleSection";
import { ToolTracePanel } from "./ToolTracePanel";
import type { ChatResponse } from "../../types/api";

interface AbstentionNoticeProps {
  response: ChatResponse & { grounding_status: "not_supported" };
}

// Deliberately distinct from GroundedAnswerCard -- an abstention is not
// "just another paragraph of chat text". Amber/warning framing, an
// explicit heading, and the agent's literal not-found message, so the
// difference between "answered" and "declined to answer" is unmistakable
// at a glance, which is the whole point of ContextIQ's grounding gate.
export function AbstentionNotice({ response }: AbstentionNoticeProps) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <p className="text-sm font-semibold text-amber-800">No grounded answer found</p>
      <p className="mt-2 text-sm text-amber-900">{response.answer}</p>

      {response.trace.length > 0 && (
        <div className="mt-3">
          <CollapsibleSection title="Agent Activity">
            <ToolTracePanel trace={response.trace} />
          </CollapsibleSection>
        </div>
      )}
    </div>
  );
}
