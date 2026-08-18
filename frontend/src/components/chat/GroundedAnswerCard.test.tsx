import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { GroundedAnswerCard } from "./GroundedAnswerCard";
import type { ChatResponse } from "../../types/api";

function makeResponse(
  overrides: Partial<Omit<ChatResponse, "grounding_status">> & { grounding_status?: "supported" | "partial" } = {},
): ChatResponse & { grounding_status: "supported" | "partial" } {
  return {
    question: "Who owns the orders dataset?",
    answer: "The orders dataset is owned by Sales Engineering.",
    grounding_status: "supported",
    sources: [{ label: "orders ownership (catalog metadata)", asset_id: "orders", source_type: "owner" }],
    evidence: [
      { source_type: "owner", title: "orders", asset_id: "orders", detail: "orders is owned by Sales Engineering", citation: "orders ownership (catalog metadata)" },
    ],
    trace: [
      { tool: "get_owner", input: { asset_id: "orders" }, output_summary: "Lookup returned the Sales Engineering owner record.", timestamp: "2026-01-01T00:00:00Z", evidence_count: 1 },
    ],
    ...overrides,
  };
}

function renderCard(response: ChatResponse & { grounding_status: "supported" | "partial" }) {
  return render(
    <MemoryRouter>
      <GroundedAnswerCard response={response} />
    </MemoryRouter>,
  );
}

describe("GroundedAnswerCard", () => {
  it("shows the supported badge and answer text for a supported response", () => {
    renderCard(makeResponse({ grounding_status: "supported" }));
    expect(screen.getByText("Grounded in ContextIQ evidence")).toBeInTheDocument();
    expect(screen.getByText("The orders dataset is owned by Sales Engineering.")).toBeInTheDocument();
  });

  it("shows the partial badge, distinct from supported, for a partial response", () => {
    renderCard(makeResponse({ grounding_status: "partial" }));
    expect(screen.getByText("Answered from partial evidence")).toBeInTheDocument();
    expect(screen.queryByText("Grounded in ContextIQ evidence")).not.toBeInTheDocument();
  });

  it("renders each source as a link to its asset", () => {
    renderCard(makeResponse());
    const link = screen.getByRole("link", { name: "orders ownership (catalog metadata)" });
    expect(link).toHaveAttribute("href", "/assets/orders");
  });

  it("reveals evidence and agent activity only after expanding, and never renders reasoning content", async () => {
    const user = userEvent.setup();
    renderCard(makeResponse());

    // Collapsed by default.
    expect(screen.queryByText("get_owner")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /agent activity/i }));
    expect(screen.getByText("get_owner")).toBeInTheDocument();
    expect(screen.getByText("Found 1 result(s)")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /evidence/i }));
    expect(screen.getByText("orders is owned by Sales Engineering")).toBeInTheDocument();

    // The whole point of the "Agent Activity" panel is observable tool
    // execution only -- never the model's hidden reasoning.
    const rendered = document.body.textContent ?? "";
    expect(rendered).not.toMatch(/<think>/i);
    expect(rendered).not.toMatch(/reasoning_content/i);
    expect(rendered).not.toMatch(/chain of thought/i);
  });
});
