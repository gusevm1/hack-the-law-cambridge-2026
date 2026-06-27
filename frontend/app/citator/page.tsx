"use client";

// Open Citator — one flow, two stages: RETRIEVE then ANALYZE.
//   Retrieve: resolve a case → /graph (the inbound treatment network) + /risk (the
//             verdict). Click any node for the grounding receipt.
//   Analyze:  /triage tiers every retrieved edge (deep|shallow|mention, nothing
//             dropped), grouped by proposition; then /verdict reads it for *your* use.
// All endpoints are public + DB-backed (golden fallback offline). See app/src/htl/
// routes/{resolve,graph,risk,triage,verdict}.py.
import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useAuth } from "../../lib/auth";
import { AccountMenu } from "../../components/account-menu";
import { CitationGraph } from "../../components/citation-graph";
import { SourceCard } from "../../components/source-card";
import { VerdictBadge } from "../../components/verdict-badge";
import VerdictStep from "./analyze/steps/verdict";
import {
  caseGraph,
  caseRisk,
  caseTriage,
  resolve,
  type GraphEdge,
  type GraphResult,
  type RiskResult,
  type TieredEdge,
  type TriageResult,
} from "../../lib/api";

// Seeded demo cases — one click loads the whole flow by id, skipping /resolve.
const DEMO: { name: string; id: number; tag: string }[] = [
  { name: "NYSRPA v. Bruen", id: 6480696, tag: "green" },
  { name: "Roe v. Wade", id: 108713, tag: "red" },
  { name: "Plessy v. Ferguson", id: 94508, tag: "red" },
  { name: "Bowers v. Hardwick", id: 111738, tag: "red" },
  { name: "Lochner v. New York", id: 96276, tag: "red" },
  { name: "Auer v. Robbins", id: 118089, tag: "green" },
  { name: "Emp. Div. v. Smith", id: 112404, tag: "red" },
];

const SIGNAL_DOT: Record<string, string> = {
  red: "bg-red-500",
  amber: "bg-amber-400",
  green: "bg-green-500",
  unknown: "bg-slate-400",
};

const TIER: Record<string, { label: string; note: string }> = {
  deep: { label: "Deep", note: "full analysis" },
  shallow: { label: "Shallow", note: "light pass" },
  mention: { label: "Mention", note: "surfaced, low-ranked" },
};

// Proposition spine (scope §4) — order + labels for grouping the analyze stage.
const PROP_ORDER = ["P1", "P2", "P2a", "P3", "P4", "P5", "P6", "P7", "P8"];
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
const NOISE = "—";

function groupByProposition(edges: TieredEdge[]) {
  const groups: Record<string, TieredEdge[]> = {};
  for (const e of edges) {
    const props = e.signals.propositions_engaged.length
      ? e.signals.propositions_engaged
      : [NOISE];
    for (const p of props) (groups[p] ??= []).push(e);
  }
  const ordered = [...PROP_ORDER.filter((p) => groups[p]), ...(groups[NOISE] ? [NOISE] : [])];
  return ordered.map((id) => ({
    id,
    label: id === NOISE ? "No proposition (noise / bare cite)" : `${id} · ${PROP_LABELS[id] ?? ""}`,
    edges: groups[id],
  }));
}

const API_DOWN = "Couldn't reach the citator API — is the backend running on :8080?";

export default function Citator() {
  const { session } = useAuth();
  const email = session?.user?.email ?? null;
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphResult | null>(null);
  const [risk, setRisk] = useState<RiskResult | null>(null);
  const [triage, setTriage] = useState<TriageResult | null>(null);
  const [selected, setSelected] = useState<GraphEdge | null>(null);
  const [hideNeutral, setHideNeutral] = useState(false);

  const load = useCallback(async (id: number) => {
    setError(null);
    setNote(null);
    setSelected(null);
    setLoading(true);
    try {
      const [g, r, t] = await Promise.all([caseGraph(id), caseRisk(id), caseTriage(id)]);
      setGraph(g);
      setRisk(r);
      setTriage(t);
    } catch {
      setError(API_DOWN);
      setGraph(null);
      setRisk(null);
      setTriage(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => void load(6480696), 0); // open on Bruen — the headline case
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

  // The clicked graph edge carries no case name (that's on the node) — resolve it.
  const selNode =
    selected && graph ? graph.nodes.find((n) => n.case_id === selected.citing_id) : null;

  const groups = triage ? groupByProposition(triage.edges) : [];
  const pct = (n: number) => (triage && triage.total ? (n / triage.total) * 100 : 0);

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <div className="mx-auto w-full max-w-7xl px-5 py-8">
        <header className="mb-6 flex items-start justify-between gap-4">
          <div>
            <div className="mb-3 flex items-center gap-2.5">
              <Image
                src="/logo.png"
                alt="CiteMeRight"
                width={28}
                height={28}
                priority
                className="h-7 w-7 rounded-[9px] ring-1 ring-white/15"
              />
              <span className="text-sm font-semibold tracking-tight text-white">CiteMeRight</span>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-white">
              Open Citator — is it still good law?
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              First we <span className="text-slate-200">retrieve</span> every case that cites
              this one; then we <span className="text-slate-200">analyze</span> how each treats it.
              Every signal is grounded — click any source to read the passage and follow it. Not
              legal advice.{" "}
              <Link href="/assistant" className="text-slate-200 underline underline-offset-2 hover:text-white">
                Try the assistant →
              </Link>
            </p>
          </div>
          {email ? (
            <AccountMenu email={email} />
          ) : (
            <Link
              href="/"
              className="shrink-0 rounded-full border border-white/15 px-4 py-1.5 text-sm text-slate-200 transition hover:bg-white/10"
            >
              Sign in
            </Link>
          )}
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
              <span className={`h-1.5 w-1.5 rounded-full ${SIGNAL_DOT[c.tag] ?? "bg-slate-400"}`} />
              {c.name}
            </button>
          ))}
        </div>

        {error && <p className="mt-6 text-sm text-red-400">{error}</p>}
        {note && <p className="mt-4 text-sm text-slate-400">{note}</p>}

        {/* ───────────────────────── STAGE 1 · RETRIEVE ───────────────────────── */}
        {graph && risk && (
          <section className="mt-8">
            <StageHeading
              n={1}
              title="Retrieve"
              sub={`${triage?.total ?? graph.nodes.length - 1} sources cite this case`}
            />
            <div className="mt-4 grid grid-cols-1 gap-5 lg:grid-cols-[1fr_360px]">
              {/* Network */}
              <div className="relative h-[560px] overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40">
                <div className="absolute left-4 top-4 z-10 flex items-center gap-3 text-xs">
                  <Legend />
                  <button
                    type="button"
                    onClick={() => setHideNeutral((v) => !v)}
                    className={`rounded-full px-3 py-1 transition ${
                      hideNeutral
                        ? "bg-white/15 text-white ring-1 ring-white/30"
                        : "bg-white/5 text-slate-300 ring-1 ring-white/10 hover:bg-white/10"
                    }`}
                  >
                    {hideNeutral ? "Treated only" : "Hide neutral"}
                  </button>
                </div>
                {loading ? (
                  <div className="flex h-full items-center justify-center text-sm text-slate-500">
                    Loading network…
                  </div>
                ) : (
                  <CitationGraph graph={graph} onSelect={setSelected} hideNeutral={hideNeutral} />
                )}
              </div>

              {/* Verdict + evidence */}
              <aside className="flex flex-col gap-4">
                <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
                  <VerdictBadge signal={risk.signal} score={risk.risk_score} />
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
                  <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">
                    Evidence
                  </h3>
                  {selected ? (
                    <SourceCard
                      caseName={selNode?.case_name ?? "Selected case"}
                      meta={[selNode?.court, selNode?.date_filed].filter(Boolean).join("  ·  ")}
                      badge={{
                        label:
                          (selected.treatment ?? "neutral citation") +
                          (selected.on_other_grounds ? " · on other grounds" : ""),
                        tone: selected.polarity,
                      }}
                      quote={selected.quote}
                      sourceUrl={selected.source_url}
                    />
                  ) : (
                    <p className="text-sm text-slate-500">
                      Click any case in the network to read the passage that grounds its
                      treatment — and follow it to the original judgment.
                    </p>
                  )}
                </div>
              </aside>
            </div>
          </section>
        )}

        {/* ───────────────────────── STAGE 2 · ANALYZE ───────────────────────── */}
        {triage && (
          <section className="mt-10">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <StageHeading
                n={2}
                title="Analyze"
                sub={`${triage.total} citations tiered by depth — nothing dropped`}
              />
              <Link
                href="/citator/analyze"
                className="text-xs font-medium text-slate-200 underline underline-offset-2 hover:text-white"
              >
                Full step-by-step pipeline · per-proposition evolution + deep reads →
              </Link>
            </div>

            {/* Funnel */}
            <div className="mt-4 rounded-2xl border border-white/10 bg-slate-900/40 p-5">
              <div className="flex h-3 w-full overflow-hidden rounded-full bg-white/10">
                <div className="bg-emerald-500" style={{ width: `${pct(triage.counts.deep)}%` }} />
                <div className="bg-yellow-400" style={{ width: `${pct(triage.counts.shallow)}%` }} />
                <div className="bg-slate-400" style={{ width: `${pct(triage.counts.mention)}%` }} />
              </div>
              <div className="mt-3 flex flex-wrap gap-4 text-xs">
                {(["deep", "shallow", "mention"] as const).map((t) => (
                  <span key={t} className="flex items-center gap-1.5">
                    <span
                      className={`inline-block h-2.5 w-2.5 rounded-full ${
                        t === "deep"
                          ? "bg-emerald-500"
                          : t === "shallow"
                            ? "bg-yellow-400"
                            : "bg-slate-400"
                      }`}
                    />
                    <span className="font-medium capitalize text-slate-200">{t}</span>
                    <span className="tabular-nums text-slate-400">{triage.counts[t]}</span>
                    <span className="text-slate-500">· {TIER[t].note}</span>
                  </span>
                ))}
              </div>
            </div>

            {/* Grouped by proposition */}
            <div className="mt-5 space-y-6">
              {groups.map((g) => (
                <div key={g.id}>
                  <h3 className="mb-2 text-sm font-semibold text-slate-200">{g.label}</h3>
                  <div className="space-y-3">
                    {g.edges.map((e, i) => (
                      <SourceCard
                        key={`${g.id}-${i}`}
                        caseName={e.citing_case.case_name}
                        meta={[e.citing_case.court, e.citing_case.date_filed, e.citation]
                          .filter(Boolean)
                          .join("  ·  ")}
                        badge={{ label: TIER[e.tier]?.label ?? e.tier, tone: e.tier }}
                        quote={e.passage}
                        sourceUrl={e.opinion_url}
                        chips={e.reasons}
                        muted={e.tier === "mention"}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* The payoff — use-aware verdict */}
            <div className="mt-8">
              <VerdictStep caseId={triage.case.case_id} active={true} />
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

function StageHeading({ n, title, sub }: { n: number; title: string; sub: string }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-white">
        {n}
      </span>
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <span className="text-sm text-slate-500">{sub}</span>
    </div>
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
