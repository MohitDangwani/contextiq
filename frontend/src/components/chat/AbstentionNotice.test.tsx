import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AbstentionNotice } from "./AbstentionNotice";
import type { ChatResponse } from "../../types/api";

const NOT_FOUND_MESSAGE =
  "I could not find information about that in ContextIQ's available data (metadata, lineage, quality, business definitions, or documentation).";

function makeResponse(
  overrides: Partial<Omit<ChatResponse, "grounding_status">> = {},
): ChatResponse & { grounding_status: "not_supported" } {
  return {
    question: "What is the capital of France?",
    answer: NOT_FOUND_MESSAGE,
    grounding_status: "not_supported",
    sources: [],
    evidence: [],
    trace: [],
    ...overrides,
  };
}

describe("AbstentionNotice", () => {
  it("renders a distinct 'no grounded answer' heading, not just the raw message as plain text", () => {
    render(<AbstentionNotice response={makeResponse()} />);
    expect(screen.getByText("No grounded answer found")).toBeInTheDocument();
    expect(screen.getByText(NOT_FOUND_MESSAGE)).toBeInTheDocument();
  });

  it("does not render an Agent Activity panel when no tools were called", () => {
    render(<AbstentionNotice response={makeResponse({ trace: [] })} />);
    expect(screen.queryByRole("button", { name: /agent activity/i })).not.toBeInTheDocument();
  });

  it("shows Agent Activity (observable actions only) when the agent did call tools before abstaining", () => {
    render(
      <AbstentionNotice
        response={makeResponse({
          trace: [
            { tool: "search_assets", input: { domain: "geography" }, output_summary: "No matching datasets found.", timestamp: "2026-01-01T00:00:00Z", evidence_count: 0 },
          ],
        })}
      />,
    );
    expect(screen.getByRole("button", { name: /agent activity/i })).toBeInTheDocument();
  });
});
