// Shared citing-source receipt: one card for a case that cites the target — the
// treatment/tier badge, the grounding passage, and the click-through to the source
// opinion. Used by BOTH the retrieve evidence panel (a clicked graph edge) and the
// analyze edge list (a triaged edge), so the receipt looks the same everywhere.
//
// `tone` spans polarity (negative|positive|neutral, from /graph treatment) and triage
// tier (deep|shallow|mention) — the colour vocabulary lives here, once.
const TONE: Record<string, string> = {
  negative: "bg-red-500/15 text-red-300 ring-1 ring-red-500/40",
  positive: "bg-green-500/15 text-green-300 ring-1 ring-green-500/40",
  neutral: "bg-slate-500/15 text-slate-300 ring-1 ring-white/15",
  deep: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/40",
  shallow: "bg-yellow-500/15 text-yellow-200 ring-1 ring-yellow-500/30",
  mention: "bg-slate-500/15 text-slate-400 ring-1 ring-white/10",
};

export function SourceCard({
  caseName,
  meta,
  badge,
  quote,
  sourceUrl,
  chips,
  muted = false,
}: {
  caseName: string | null;
  meta?: string;
  badge?: { label: string; tone: string };
  quote: string | null;
  sourceUrl?: string | null;
  chips?: string[];
  muted?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border border-white/10 bg-slate-900/50 p-4 ${
        muted ? "opacity-70" : ""
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        {badge && (
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
              TONE[badge.tone] ?? TONE.neutral
            }`}
          >
            {badge.label}
          </span>
        )}
        <span className="text-sm font-medium text-white">{caseName ?? "Unknown case"}</span>
        {meta && <span className="text-xs text-slate-400">{meta}</span>}
      </div>

      {quote ? (
        <blockquote className="mt-3 border-l-2 border-white/20 pl-3 text-sm italic leading-relaxed text-slate-300">
          “{quote}”
        </blockquote>
      ) : (
        <p className="mt-3 text-sm text-slate-500">No passage on record for this cite.</p>
      )}

      {chips && chips.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {chips.map((c, i) => (
            <li
              key={i}
              className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[11px] text-slate-400"
            >
              {c}
            </li>
          ))}
        </ul>
      )}

      {sourceUrl && (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-slate-200 underline underline-offset-2 hover:text-white"
        >
          View source opinion ↗
        </a>
      )}
    </div>
  );
}
