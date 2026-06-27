"use client";

// Public citator showcase: resolve a case → /graph (the treatment network) +
// /risk (the verdict) → click any citer for the grounding receipt. All three
// endpoints are unauthenticated (see app/src/htl/routes/{resolve,risk,graph}.py).
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CitationGraph } from "../../components/citation-graph";
import {
  caseGraph,
  caseRisk,
  resolve,
  type GraphEdge,
  type GraphResult,
  type RiskResult,
} from "../../lib/api";

// Seeded demo cases — one click loads graph+risk by id, skipping /resolve.
const DEMO: { name: string; id: number; tag: string }[] = [
  { name: "NYSRPA v. Bruen", id: 6480696, tag: "green" },
  { name: "Roe v. Wade", id: 108713, tag: "red" },
  { name: "Plessy v. Ferguson", id: 94508, tag: "red" },
  { name: "Bowers v. Hardwick", id: 111738, tag: "red" },
  { name: "Lochner v. New York", id: 96276, tag: "red" },
  { name: "Auer v. Robbins", id: 118089, tag: "green" },
  { name: "Emp. Div. v. Smith", id: 112404, tag: "red" },
];

const SIGNAL: Record<string, { dot: string; text: string; label: string }> = {
  red: { dot: "bg-red-500", text: "text-red-400", label: "No longer good law" },
  amber: { dot: "bg-amber-400", text: "text-amber-300", label: "Good, but eroding" },
  green: { dot: "bg-green-500", text: "text-green-400", label: "Still good law" },
  unknown: { dot: "bg-slate-400", text: "text-slate-300", label: "Unknown" },
};

const POL_BADGE: Record<string, string> = {
  negative: "bg-red-500/15 text-red-300 ring-1 ring-red-500/40",
  positive: "bg-green-500/15 text-green-300 ring-1 ring-green-500/40",
  neutral: "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30",
};

const API_DOWN = "Couldn't reach the citator API — is the backend running on :8080?";

export default function Citator() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphResult | null>(null);
  const [risk, setRisk] = useState<RiskResult | null>(null);
  const [selected, setSelected] = useState<GraphEdge | null>(null);
  const [negativeOnly, setNegativeOnly] = useState(false);

  const load = useCallback(async (id: number) => {
    setError(null);
    setNote(null);
    setSelected(null);
    setLoading(true);
    try {
      const [g, r] = await Promise.all([caseGraph(id), caseRisk(id)]);
      setGraph(g);
      setRisk(r);
    } catch {
      setError(API_DOWN);
      setGraph(null);
      setRisk(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Open on Bruen — the headline case. Deferred a tick so the initial demo
    // fetch doesn't set state synchronously inside the effect body.
    const t = setTimeout(() => void load(6480696), 0);
    return () => clearTimeout(t);
  }, [load]);

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q || loading) return;
    setError(null);
    setNote(null);
    setLoading(true);
    try {
      const res = await resolve(q);
      if (!res.found || res.case_id == null) {
        setNote(`No such case found for “${q}”.`);
        return;
      }
      if (res.ambiguous) setNote("Multiple matches — showing the top hit.");
      await load(res.case_id);
    } catch {
      setError(API_DOWN);
    } finally {
      setLoading(false);
    }
  }

  const sig = SIGNAL[risk?.signal ?? "unknown"] ?? SIGNAL.unknown;

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <div className="mx-auto w-full max-w-7xl px-5 py-8">
        <header className="mb-6">
          <h1 className="bg-gradient-to-r from-white to-slate-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
            Open Citator — is it still good law?
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Every signal is grounded: click any case in the network to read the exact
            passage that treats it, and follow it to the source. Not legal advice.{" "}
            <Link href="/assistant" className="text-sky-400 underline-offset-2 hover:underline">
              Try the assistant →
            </Link>
          </p>
        </header>

        {/* Search + demo chips */}
        <form onSubmit={onSearch} className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search a case by name or citation  ·  e.g. 597 U.S. 1"
            className="flex-1 rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm outline-none placeholder:text-slate-500 focus:border-white/30"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="rounded-full bg-white px-6 py-2.5 text-sm font-medium text-slate-900 transition hover:bg-slate-200 disabled:opacity-40"
          >
            Check
          </button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          {DEMO.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => load(c.id)}
              disabled={loading}
              className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs transition hover:bg-white/10 disabled:opacity-40"
            >
              <span className={`h-1.5 w-1.5 rounded-full ${SIGNAL[c.tag]?.dot ?? "bg-slate-400"}`} />
              {c.name}
            </button>
          ))}
        </div>

        {error && <p className="mt-6 text-sm text-red-400">{error}</p>}
        {note && <p className="mt-4 text-sm text-slate-400">{note}</p>}

        {graph && risk && (
          <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-[1fr_360px]">
            {/* Network */}
            <section className="relative h-[560px] overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40">
              <div className="absolute left-4 top-4 z-10 flex items-center gap-3 text-xs">
                <Legend />
                <button
                  type="button"
                  onClick={() => setNegativeOnly((v) => !v)}
                  className={`rounded-full px-3 py-1 transition ${
                    negativeOnly
                      ? "bg-red-500/20 text-red-300 ring-1 ring-red-500/40"
                      : "bg-white/5 text-slate-300 ring-1 ring-white/10 hover:bg-white/10"
                  }`}
                >
                  {negativeOnly ? "Showing negative only" : "Negative only"}
                </button>
              </div>
              {loading ? (
                <div className="flex h-full items-center justify-center text-sm text-slate-500">
                  Loading network…
                </div>
              ) : (
                <CitationGraph graph={graph} onSelect={setSelected} negativeOnly={negativeOnly} />
              )}
            </section>

            {/* Verdict + evidence */}
            <aside className="flex flex-col gap-4">
              <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
                <div className="flex items-center gap-2">
                  <span className={`h-2.5 w-2.5 rounded-full ${sig.dot}`} />
                  <span className={`text-sm font-semibold ${sig.text}`}>{sig.label}</span>
                  <span className="ml-auto text-xs text-slate-500">
                    risk {risk.risk_score.toFixed(2)}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium text-white">
                  {risk.case.case_name ?? `Case ${risk.case.case_id}`}
                </p>
                <p className="text-xs text-slate-400">
                  {[risk.case.citation, risk.case.court, risk.case.date_filed]
                    .filter(Boolean)
                    .join("  ·  ")}
                </p>
                <p className="mt-3 text-sm text-slate-300">{risk.risk_rationale}</p>
                {risk.ground_truth.overruled_by && (
                  <p className="mt-2 text-xs font-medium text-red-400">
                    Ground truth: overruled by {risk.ground_truth.overruled_by}
                  </p>
                )}
                <div className="mt-4 flex gap-4 border-t border-white/10 pt-3 text-xs text-slate-400">
                  <span>
                    <span className="text-white">{risk.negative_treatments.length}</span> negative
                  </span>
                  <span>
                    <span className="text-white">{risk.positive_signal.approving_cites}</span> approving
                  </span>
                  <span>
                    <span className="text-white">{risk.positive_signal.total_citing}</span> citing
                  </span>
                </div>
              </div>

              <div className="flex-1 rounded-2xl border border-white/10 bg-slate-900/60 p-5">
                <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Evidence
                </h2>
                {selected ? (
                  <div className="mt-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          POL_BADGE[selected.polarity]
                        }`}
                      >
                        {selected.treatment ?? "neutral citation"}
                        {selected.on_other_grounds ? " · on other grounds" : ""}
                      </span>
                      {selected.confidence != null && (
                        <span className="text-[11px] text-slate-500">
                          {Math.round(selected.confidence * 100)}% conf
                        </span>
                      )}
                    </div>
                    {selected.quote ? (
                      <blockquote className="mt-3 border-l-2 border-white/20 pl-3 text-sm italic leading-relaxed text-slate-300">
                        “{selected.quote}”
                      </blockquote>
                    ) : (
                      <p className="mt-3 text-sm text-slate-500">
                        Cited without a classified treatment passage.
                      </p>
                    )}
                    {selected.source_url && (
                      <a
                        href={selected.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-sky-400 hover:text-sky-300"
                      >
                        View source opinion ↗
                      </a>
                    )}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-500">
                    Click any case in the network to read the passage that grounds its
                    treatment — and follow it to the original judgment.
                  </p>
                )}
              </div>
            </aside>
          </div>
        )}
      </div>
    </main>
  );
}

function Legend() {
  const items = [
    { c: "bg-red-500", l: "Negative" },
    { c: "bg-green-500", l: "Approving" },
    { c: "bg-slate-400", l: "Neutral" },
  ];
  return (
    <div className="flex items-center gap-3 rounded-full bg-white/5 px-3 py-1 ring-1 ring-white/10">
      {items.map((i) => (
        <span key={i.l} className="flex items-center gap-1.5 text-slate-300">
          <span className={`h-1.5 w-1.5 rounded-full ${i.c}`} />
          {i.l}
        </span>
      ))}
    </div>
  );
}
