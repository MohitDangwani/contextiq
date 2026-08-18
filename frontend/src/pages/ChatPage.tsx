import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { ChatComposer } from "../components/chat/ChatComposer";
import { ThinkingIndicator } from "../components/chat/ThinkingIndicator";
import { GroundedAnswerCard } from "../components/chat/GroundedAnswerCard";
import { AbstentionNotice } from "../components/chat/AbstentionNotice";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { ask } from "../services/chatService";
import { ApiError } from "../services/httpClient";
import type { ChatResponse } from "../types/api";

interface Turn {
  id: string;
  question: string;
  response?: ChatResponse;
  error?: string;
}

export function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: ask,
    onSuccess: (response, question) => {
      setTurns((prev) => [...prev, { id: crypto.randomUUID(), question, response }]);
      setPendingQuestion(null);
    },
    onError: (err, question) => {
      const message = err instanceof ApiError ? err.message : "Could not reach ContextIQ's backend.";
      setTurns((prev) => [...prev, { id: crypto.randomUUID(), question, error: message }]);
      setPendingQuestion(null);
    },
  });

  function handleSubmit(question: string) {
    setPendingQuestion(question);
    mutation.mutate(question);
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Ask ContextIQ</h1>
        <p className="mt-1 text-sm text-slate-500">
          Every answer is grounded in real catalog evidence — ownership, PII, quality, lineage, business
          definitions, and documentation — and the agent explicitly says so when it can&apos;t find a
          supported answer, instead of guessing.
        </p>
      </div>

      <div className="flex flex-col gap-4">
        {turns.length === 0 && !pendingQuestion && (
          <EmptyState
            message="Ask a question to get started"
            hint='Try "Who owns the orders dataset?" or "Is the payments dataset trustworthy?"'
          />
        )}

        {turns.map((turn) => (
          <div key={turn.id} className="flex flex-col gap-2">
            <div className="self-end rounded-lg bg-slate-900 px-3 py-2 text-sm text-white">{turn.question}</div>
            {turn.response &&
              (turn.response.grounding_status === "not_supported" ? (
                <AbstentionNotice response={turn.response as ChatResponse & { grounding_status: "not_supported" }} />
              ) : (
                <GroundedAnswerCard
                  response={turn.response as ChatResponse & { grounding_status: "supported" | "partial" }}
                />
              ))}
            {turn.error && <ErrorState message={turn.error} />}
          </div>
        ))}

        {pendingQuestion && (
          <div className="flex flex-col gap-2">
            <div className="self-end rounded-lg bg-slate-900 px-3 py-2 text-sm text-white">{pendingQuestion}</div>
            <ThinkingIndicator />
          </div>
        )}
      </div>

      <div className="sticky bottom-4">
        <ChatComposer onSubmit={handleSubmit} disabled={mutation.isPending} />
      </div>
    </div>
  );
}
