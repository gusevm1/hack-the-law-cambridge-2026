// Shared signal badge — the good-law verdict, one vocabulary across the retrieve
// (/risk · /graph) and analyze (/verdict) surfaces so they can never read differently.
const SIGNAL: Record<string, { dot: string; text: string; label: string }> = {
  red: { dot: "bg-red-500", text: "text-red-400", label: "No longer good law" },
  amber: { dot: "bg-amber-400", text: "text-amber-300", label: "Good, but eroding" },
  green: { dot: "bg-green-500", text: "text-green-400", label: "Still good law" },
  unknown: { dot: "bg-slate-400", text: "text-slate-300", label: "Unknown" },
};

export function VerdictBadge({ signal, score }: { signal: string; score?: number }) {
  const s = SIGNAL[signal] ?? SIGNAL.unknown;
  return (
    <div className="flex items-center gap-2">
      <span className={`h-2.5 w-2.5 rounded-full ${s.dot}`} />
      <span className={`text-sm font-semibold ${s.text}`}>{s.label}</span>
      {score != null && (
        <span className="ml-auto text-xs text-slate-500">risk {score.toFixed(2)}</span>
      )}
    </div>
  );
}
