// Relation step (Feature 4 / B) — per-proposition evolution + risk + trajectory.
// Renders GET /cases/{id}/propositions: each proposition's signal, the grounded
// "what changed" narrative, a CSS treatment timeline (erosion-bar idiom), and the
// trajectory badges (circuit split · cert watch · close-to-overruled). The page
// fetches lazily and hands the result in; this file owns only the rendering.
import type {
  CircuitSplit,
  CertStatus,
  CloseToOverruled,
  PropositionsResult,
  PropositionVerdict,
  TimelinePoint,
} from "@/lib/api";

const SIGNAL: Record<string, { dot: string; ring: string; label: string }> = {
  green: { dot: "bg-green-500", ring: "border-green-500/30", label: "Good law" },
  amber: { dot: "bg-yellow-400", ring: "border-yellow-400/40", label: "Eroding / watch" },
  red: { dot: "bg-red-500", ring: "border-red-500/40", label: "High risk" },
  unknown: { dot: "bg-gray-400", ring: "border-black/10 dark:border-white/15", label: "Unknown" },
};

// Treatment-point colour by polarity (−1 negative · 0 neutral · +1 approving).
const POLARITY = {
  "-1": "bg-red-500",
  "0": "bg-gray-400",
  "1": "bg-emerald-500",
} as const;

export function RelationStep({
  data,
  loading,
  error,
}: {
  data: PropositionsResult | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading)
    return <p className="text-sm opacity-50">Aggregating per-proposition verdicts…</p>;
  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!data) return null;

  return (
    <section className="space-y-6">
      {/* Operative rule — the headline the litigator actually wants */}
      <div className="rounded-3xl border border-black/10 p-6 dark:border-white/15">
        <h2 className="text-xs font-semibold uppercase tracking-wide opacity-60">
          Operative rule
        </h2>
        <p className="mt-2 text-base font-medium">{data.operative_rule}</p>
        <p className="mt-2 text-xs opacity-50">
          {data.propositions.length} proposition{data.propositions.length === 1 ? "" : "s"} tracked
          · as of {data.as_of}. Treatment attaches to each proposition separately — that's the unlock.
        </p>
      </div>

      {data.propositions.map((p) => (
        <PropositionCard key={p.proposition_id} p={p} />
      ))}
    </section>
  );
}

function PropositionCard({ p }: { p: PropositionVerdict }) {
  const sig = SIGNAL[p.signal] ?? SIGNAL.unknown;
  return (
    <div className={`rounded-2xl border p-5 ${sig.ring}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`inline-block h-3 w-3 rounded-full ${sig.dot}`} />
        <span className="text-sm font-semibold">
          {p.proposition_id} · {p.label}
        </span>
        <span className="rounded-full bg-black/5 px-2 py-0.5 text-[11px] capitalize dark:bg-white/10">
          {p.status}
        </span>
        <span className="text-[11px] uppercase tracking-wide opacity-50">{sig.label}</span>
        <span className="ml-auto text-xs opacity-50">risk {p.risk_score.toFixed(2)}</span>
      </div>

      <p className="mt-1 text-xs opacity-60">{p.summary}</p>
      <p className="mt-3 text-sm opacity-85">{p.what_changed}</p>

      {/* Trajectory badges */}
      <div className="mt-3 flex flex-wrap gap-2">
        {p.circuit_split && <SplitBadge split={p.circuit_split} />}
        {p.cert && <CertBadge cert={p.cert} />}
        <C2OBadge c2o={p.close_to_overruled} />
      </div>

      <Timeline points={p.timeline} />

      {p.supporting_edges.length > 0 && (
        <p className="mt-3 text-[11px] opacity-50">Backed by: {p.supporting_edges.join(" · ")}</p>
      )}
    </div>
  );
}

// CSS timeline — chronological treatments, colour ∝ polarity (the erosion-bar idiom).
function Timeline({ points }: { points: TimelinePoint[] }) {
  if (points.length === 0) return null;
  return (
    <div className="mt-4">
      <h3 className="text-[10px] font-semibold uppercase tracking-wide opacity-50">Timeline</h3>
      <div className="mt-2 flex items-end gap-3 overflow-x-auto">
        {points.map((t, i) => (
          <div key={i} className="flex w-16 shrink-0 flex-col items-center gap-1">
            <span className="truncate text-[10px] opacity-60" title={t.case_name ?? ""}>
              {t.treatment}
            </span>
            <div
              className={`h-10 w-2 rounded ${POLARITY[String(t.polarity) as keyof typeof POLARITY] ?? POLARITY["0"]}`}
              title={`${t.case_name ?? "?"} (${t.court ?? "?"}) — ${t.treatment}`}
            />
            <span className="text-[10px] tabular-nums opacity-60">{t.year}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SplitBadge({ split }: { split: CircuitSplit }) {
  if (!split.present) return null;
  return (
    <span
      className="rounded-full bg-yellow-500/15 px-2 py-0.5 text-[11px] font-medium text-yellow-700 dark:text-yellow-400"
      title={split.summary}
    >
      ⚖ Circuit split — {split.follows.join(", ")} follow · {split.limits.join(", ")} limit
    </span>
  );
}

function CertBadge({ cert }: { cert: CertStatus }) {
  const granted = cert.granted;
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
        granted
          ? "bg-red-500/15 text-red-600 dark:text-red-400"
          : "bg-black/[0.06] opacity-80 dark:bg-white/10"
      }`}
      title={`${cert.case_name ?? ""}${cert.question ? ` — ${cert.question}` : ""}\n${cert.source ?? ""} · as of ${cert.as_of ?? "?"}`}
    >
      🏛 Cert {granted ? "GRANTED" : "watch (pending)"}
    </span>
  );
}

function C2OBadge({ c2o }: { c2o: CloseToOverruled }) {
  // Abstention is a feature: "needs review" reads amber, not a confident verdict.
  const review = !c2o.flag && c2o.rationale.toLowerCase().includes("review");
  const cls = c2o.flag
    ? "bg-red-500/15 text-red-600 dark:text-red-400"
    : review
      ? "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400"
      : "bg-black/[0.06] opacity-70 dark:bg-white/10";
  const label = c2o.flag ? "Close to overruled" : review ? "Needs review" : "Not close to overruled";
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`} title={c2o.rationale}>
      {label} · {Math.round(c2o.confidence * 100)}%
    </span>
  );
}
