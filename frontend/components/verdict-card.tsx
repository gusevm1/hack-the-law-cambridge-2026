import type { RiskResult } from "../lib/api";

const SIGNAL: Record<string, { dot: string; label: string }> = {
  red: { dot: "bg-red-500", label: "High risk" },
  amber: { dot: "bg-yellow-400", label: "Eroding" },
  green: { dot: "bg-green-500", label: "Good law" },
  unknown: { dot: "bg-gray-400", label: "Unknown" },
};

export function VerdictCard({ risk, note }: { risk: RiskResult; note?: string | null }) {
  const sig = SIGNAL[risk.signal] ?? SIGNAL.unknown;
  const { case: c, ground_truth: gt, positive_signal: pos } = risk;

  return (
    <section className="mt-6 rounded-3xl border border-black/10 p-6 dark:border-white/15">
      {note && <p className="mb-3 text-xs opacity-60">{note}</p>}

      {/* Signal + status */}
      <div className="flex items-center gap-3">
        <span className={`inline-block h-3 w-3 rounded-full ${sig.dot}`} />
        <span className="text-base font-semibold capitalize">{risk.status}</span>
        <span className="text-xs uppercase tracking-wide opacity-50">
          {sig.label}
        </span>
        <span className="ml-auto text-xs opacity-50">
          risk {risk.risk_score.toFixed(2)}
        </span>
      </div>
      <p className="mt-2 text-sm opacity-80">{risk.risk_rationale}</p>

      {/* Case header */}
      <div className="mt-4 border-t border-black/10 pt-4 dark:border-white/10">
        <p className="text-sm font-medium">{c.case_name ?? `Case ${c.case_id}`}</p>
        <p className="text-xs opacity-60">
          {[c.citation, c.court, c.date_filed].filter(Boolean).join("  ·  ") ||
            "No metadata"}
        </p>
        {gt.overruled_by && (
          <p className="mt-2 text-sm font-medium text-red-500">
            Overruled by {gt.overruled_by}
          </p>
        )}
      </div>

      {/* Erosion trend — headline feature: CSS bars, height ∝ neg_share. */}
      <div className="mt-5">
        <h2 className="text-xs font-semibold uppercase tracking-wide opacity-60">
          Erosion trend
        </h2>
        {risk.trend.length === 0 ? (
          <p className="mt-2 text-xs opacity-50">No dated treatments.</p>
        ) : (
          <div className="mt-3 flex items-end gap-2 overflow-x-auto">
            {risk.trend.map((t) => (
              <div key={t.year} className="flex w-12 shrink-0 flex-col items-center gap-1">
                <span className="text-[10px] tabular-nums opacity-60">
                  {t.neg}/{t.pos}
                </span>
                <div className="flex h-24 w-6 items-end rounded bg-black/5 dark:bg-white/10">
                  <div
                    className="w-full rounded bg-red-500"
                    style={{
                      // height ∝ negative share, with a floor so non-zero years read.
                      height: `${Math.max(t.neg_share * 100, t.neg > 0 ? 8 : 0)}%`,
                    }}
                    title={`${(t.neg_share * 100).toFixed(0)}% negative`}
                  />
                </div>
                <span className="text-[10px] tabular-nums opacity-60">{t.year}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Negative treatments */}
      {risk.negative_treatments.length > 0 && (
        <div className="mt-5">
          <h2 className="text-xs font-semibold uppercase tracking-wide opacity-60">
            Negative treatments ({risk.negative_treatments.length})
          </h2>
          <ul className="mt-3 space-y-3">
            {risk.negative_treatments.map((t, i) => (
              <li
                key={i}
                className="rounded-xl border border-black/10 p-3 dark:border-white/10"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-[11px] font-medium text-red-600 dark:text-red-400">
                    {t.type}
                    {t.on_other_grounds ? " · on other grounds" : ""}
                  </span>
                  <span className="text-xs opacity-70">
                    {t.citing_case.case_name ?? "Unknown citing case"}
                    {t.citing_case.date_filed ? ` · ${t.citing_case.date_filed}` : ""}
                  </span>
                  {t.confidence != null && (
                    <span className="ml-auto text-[11px] opacity-50">
                      {Math.round(t.confidence * 100)}% conf
                    </span>
                  )}
                </div>
                {t.quote && (
                  <p className="mt-2 text-xs italic opacity-80">“{t.quote}”</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Positive signal */}
      <div className="mt-5 border-t border-black/10 pt-4 text-xs opacity-70 dark:border-white/10">
        Positive signal: {pos.approving_cites} approving of {pos.total_citing} citing.
      </div>
    </section>
  );
}
