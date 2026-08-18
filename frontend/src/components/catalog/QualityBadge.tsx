interface QualityBadgeProps {
  score: number | null;
}

// Buckets, not hardcoded per-asset values -- the score itself always
// comes from the live API; this only maps a numeric score to a color band.
function bucket(score: number | null): { label: string; className: string } {
  if (score === null) return { label: "No score", className: "bg-slate-100 text-slate-500 border-slate-200" };
  if (score >= 90) return { label: `${score.toFixed(0)}`, className: "bg-emerald-50 text-emerald-700 border-emerald-200" };
  if (score >= 70) return { label: `${score.toFixed(0)}`, className: "bg-amber-50 text-amber-700 border-amber-200" };
  return { label: `${score.toFixed(0)}`, className: "bg-rose-50 text-rose-700 border-rose-200" };
}

export function QualityBadge({ score }: QualityBadgeProps) {
  const { label, className } = bucket(score);
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${className}`}>Quality: {label}</span>;
}
