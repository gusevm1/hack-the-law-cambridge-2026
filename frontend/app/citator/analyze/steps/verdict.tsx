"use client";

// Verdict step (Feature 5 / C) — the payoff. POST /cases/{id}/verdict {use, intent}
// returns risk *relative to the lawyer's intended use* (see app/src/htl/routes/
// verdict.py). Self-contained: the proposition-aligned use dropdown + free-form
// intent live here, so the stepper page only swaps in <VerdictStep/>.
import { useEffect, useRef, useState } from "react";
import { caseVerdict, type VerdictResult } from "@/lib/api";

const API_DOWN = "Couldn't reach the citator API — is `just dev-api` running?";

// Mirrors USE_DEFAULTS in app/src/htl/llm/usemap.py — labels must match verbatim so
// the backend resolves the menu pick deterministically (no model call).
const USES = [
  "Public-carry right (P1)",
  "History-and-tradition test (P2/P2a)",
  "Sensitive-places restriction (P3)",
  "Assault-weapon / magazine ban (P4)",
  "Felon / §922(g) disqualification (P5)",
  "Licensing regime (P7)",
];

const PROP_LABELS: Record<string, string> = {
  P1: "Public-carry right",
  P2: "Text-history-tradition",
  P2a: "Analogue not twin",
  P3: "Sensitive places",
  P4: "Common use / AWB",
  P5: "The people / §922(g)",
  P6: "Historical era 1791/1868",
  P7: "Shall-issue licensing",
  P8: "Presumptively-lawful carve-outs",
};

const SIGNAL_TONE: Record<string, string> = {
  red: "bg-red-500/15 text-red-600 dark:text-red-400",
  amber: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  green: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  unknown: "bg-black/[0.06] opacity-70 dark:bg-white/10",
};
const SIGNAL_DOT: Record<string, string> = {
  red: "bg-red-500",
  amber: "bg-yellow-400",
  green: "bg-emerald-500",
  unknown: "bg-gray-400",
};

export default function VerdictStep({ caseId, active }: { caseId: number; active: boolean }) {
  const [use, setUse] = useState(USES[0]);
  const [intent, setIntent] = useState("");
  const [data, setData] = useState<VerdictResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ranFor = useRef<number | null>(null); // case we've auto-assessed, to avoid loops

  async function assess(u: string, i: string) {
    setLoading(true);
    setError(null);
    try {
      setData(await caseVerdict(caseId, u, i));
    } catch {
      setError(API_DOWN);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  // Auto-assess once with the default use when the user first reaches this step,
  // so it isn't empty — deterministic (menu pick, no free-form), so no model cost.
  useEffect(() => {
    if (!active || ranFor.current === caseId) return;
    ranFor.current = caseId;
    assess(use, intent);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, caseId]);

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-black/10 p-6 dark:border-white/15">
        <h2 className="text-xs font-semibold uppercase tracking-wide opacity-60">
          Is it good law — for your use?
        </h2>
        <p className="mt-2 text-sm opacity-70">
          A case can be intact on one proposition and eroded on another. Pick how you
          intend to use it; we intersect the propositions it depends on with the ones
          that are compromised.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!loading) assess(use, intent);
          }}
          className="mt-4 space-y-3"
        >
          <label className="block">
            <span className="mb-1 block text-xs opacity-60">How will you use it?</span>
            <select
              value={use}
              onChange={(e) => setUse(e.target.value)}
              className="w-full rounded-2xl border border-black/15 bg-transparent px-4 py-2 text-sm outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50"
            >
              {USES.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs opacity-60">
              Refine in your own words (optional)
            </span>
            <input
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              placeholder="e.g. as-applied challenge for a non-violent felon client"
              className="w-full rounded-2xl border border-black/15 bg-transparent px-4 py-2 text-sm outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50"
            />
          </label>
          <button
            type="submit"
            disabled={loading}
            className="rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background disabled:opacity-40"
          >
            {loading ? "Assessing…" : "Assess for this use"}
          </button>
        </form>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}
      {data && !loading && <Verdict data={data} />}
    </section>
  );
}

function Verdict({ data }: { data: VerdictResult }) {
  const risk = data.real_risk;
  const banner = risk
    ? "border-red-500/30 bg-red-500/10"
    : "border-emerald-500/30 bg-emerald-500/10";
  return (
    <>
      {/* Use-specific real-risk banner */}
      <div className={`rounded-3xl border p-6 ${banner}`}>
        <p className="flex items-center gap-2 text-sm font-semibold">
          <span className={`inline-block h-2.5 w-2.5 rounded-full ${risk ? "bg-red-500" : "bg-emerald-500"}`} />
          {risk ? "Real risk for your use" : "Safe for your use"}
        </p>
        <p className="mt-2 text-sm opacity-80">{data.risk_explanation}</p>
        <p className="mt-3 text-xs opacity-60">
          Operative rule: <span className="font-medium">{data.operative_rule}</span>
        </p>
      </div>

      {/* Composed labels */}
      {data.final_labels.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {data.final_labels.map((l, i) => (
            <li
              key={i}
              className="rounded-full bg-black/[0.05] px-2.5 py-0.5 text-[11px] opacity-80 dark:bg-white/[0.08]"
            >
              {l}
            </li>
          ))}
        </ul>
      )}

      {/* Per-proposition breakdown — engaged ones highlighted */}
      <div>
        <h3 className="mb-2 text-sm font-semibold">Per proposition</h3>
        <ul className="space-y-2">
          {data.per_proposition.map((p) => {
            const tone = SIGNAL_TONE[p.signal] ?? SIGNAL_TONE.unknown;
            return (
              <li
                key={p.proposition_id}
                className={`rounded-2xl border p-4 ${
                  p.relevant_to_use
                    ? "border-foreground/40 bg-black/[0.02] dark:bg-white/[0.04]"
                    : "border-black/10 opacity-70 dark:border-white/10"
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`inline-block h-2 w-2 rounded-full ${SIGNAL_DOT[p.signal] ?? SIGNAL_DOT.unknown}`} />
                  <span className="text-sm font-medium">
                    {p.proposition_id} · {PROP_LABELS[p.proposition_id] ?? ""}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tone}`}>
                    {p.signal}
                  </span>
                  {p.relevant_to_use && (
                    <span className="ml-auto rounded-full bg-foreground px-2 py-0.5 text-[11px] font-medium text-background">
                      relevant to your use
                    </span>
                  )}
                </div>
                <p className="mt-2 text-xs opacity-75">{p.note}</p>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Provenance */}
      <p className="text-[11px] opacity-50">
        Use mapped to {data.use.engaged_propositions.join(", ") || "—"} · {data.use.rationale} ·
        close to overruled: {data.close_to_overruled.flag ? "yes" : "no"} · as of {data.as_of}
      </p>
    </>
  );
}
