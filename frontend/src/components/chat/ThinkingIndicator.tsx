import { useEffect, useState } from "react";

// Purely cosmetic, cycling status text -- there is no streaming from the
// backend, so this is NOT tied to real agent events and never claims to
// be. It exists only because a real question takes ~7-8s (tool-calling
// loop + the grounding gate's own verification call), and a static
// spinner reads as broken over that long.
const STAGES = ["Searching the catalog…", "Gathering evidence…", "Checking groundedness…"];

export function ThinkingIndicator() {
  const [stageIndex, setStageIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setStageIndex((i) => (i + 1) % STAGES.length);
    }, 2200);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
      <span className="text-sm text-slate-500">{STAGES[stageIndex]}</span>
    </div>
  );
}
