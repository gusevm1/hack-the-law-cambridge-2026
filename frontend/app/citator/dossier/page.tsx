"use client";

// Case dossier — the whole citator in one scroll: verdict + operative rule, the
// interactive filterable graph, erosion timeline, how each holding held up
// (propositions), the grounded treatments, and the use-aware verdict. All live:
// /risk · /graph · /triage · /propositions · /verdict.
import { useCallback, useEffect, useState } from "react";
import { CitationGraph } from "../../../components/citation-graph";
import {
  caseGraph, caseRisk, caseTriage, casePropositions, caseVerdict, resolve,
  type GraphEdge, type GraphResult, type RiskResult, type TriageResult,
  type PropositionsResult, type VerdictResult,
} from "../../../lib/api";

const DEMO = [
  { name: "NYSRPA v. Bruen", id: 6480696 }, { name: "Roe v. Wade", id: 108713 },
  { name: "Plessy v. Ferguson", id: 94508 }, { name: "Bowers v. Hardwick", id: 111738 },
  { name: "Lochner v. New York", id: 96276 }, { name: "Auer v. Robbins", id: 118089 },
  { name: "Emp. Div. v. Smith", id: 112404 },
];

const SIG: Record<string, { txt: string; ring: string; glow: string; label: string; dot: string }> = {
  red: { txt: "text-red-400", ring: "ring-red-500/50", glow: "shadow-red-500/30", label: "No longer good law", dot: "bg-red-500" },
  amber: { txt: "text-amber-300", ring: "ring-amber-400/50", glow: "shadow-amber-400/30", label: "Good, but eroding", dot: "bg-amber-400" },
  green: { txt: "text-green-400", ring: "ring-green-500/50", glow: "shadow-green-500/30", label: "Still good law", dot: "bg-green-500" },
  unknown: { txt: "text-slate-300", ring: "ring-slate-500/40", glow: "shadow-slate-500/20", label: "Unknown", dot: "bg-slate-400" },
};
const sigOf = (s: string) => SIG[s] ?? SIG.unknown;

function Sparkline({ trend }: { trend: RiskResult["trend"] }) {
  if (!trend?.length) return <p className="text-xs text-slate-500">No dated treatments.</p>;
  const w = 240, h = 44, n = trend.length;
  const pts = trend.map((t, i) => [n === 1 ? w / 2 : (i / (n - 1)) * w, h - t.neg_share * h]);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  return (
    <svg width={w} height={h} className="overflow-visible">
      <path d={`${d} L${w} ${h} L0 ${h} Z`} fill="url(#g)" opacity="0.25" />
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.8" className="text-red-400" />
      {pts.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r="2" className="fill-red-400" />)}
      <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#f87171" /><stop offset="1" stopColor="transparent" /></linearGradient></defs>
    </svg>
  );
}

const Card = ({ children, className = "" }: { children: React.ReactNode; className?: string }) =>
  <section className={`rounded-2xl border border-white/10 bg-slate-900/50 ${className}`}>{children}</section>;
const H = ({ children }: { children: React.ReactNode }) =>
  <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">{children}</h2>;

export default function Dossier() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [risk, setRisk] = useState<RiskResult | null>(null);
  const [graph, setGraph] = useState<GraphResult | null>(null);
  const [triage, setTriage] = useState<TriageResult | null>(null);
  const [props, setProps] = useState<PropositionsResult | null>(null);
  const [sel, setSel] = useState<GraphEdge | null>(null);
  const [hideNeutral, setHideNeutral] = useState(true);
  const [use, setUse] = useState("");
  const [verdict, setVerdict] = useState<VerdictResult | null>(null);
  const [vLoading, setVLoading] = useState(false);

  const load = useCallback(async (id: number) => {
    setErr(null); setSel(null); setVerdict(null); setUse(""); setLoading(true);
    try {
      const [r, g, t, p] = await Promise.all([
        caseRisk(id), caseGraph(id), caseTriage(id).catch(() => null), casePropositions(id).catch(() => null),
      ]);
      setRisk(r); setGraph(g); setTriage(t); setProps(p);
    } catch { setErr("Couldn't reach the API on :8080."); setRisk(null); setGraph(null); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { const t = setTimeout(() => void load(6480696), 0); return () => clearTimeout(t); }, [load]);

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim(); if (!q || loading) return;
    setLoading(true); setErr(null);
    try {
      const id = DEMO.find((d) => d.name.toLowerCase().includes(q.toLowerCase()))?.id
        ?? (await resolve(q)).case_id;
      if (id) await load(id); else setErr(`No case found for “${q}”.`);
    } catch { setErr("Lookup failed."); } finally { setLoading(false); }
  }

  async function getVerdict(e: React.FormEvent) {
    e.preventDefault();
    if (!use.trim() || !risk || vLoading) return;
    setVLoading(true);
    try { setVerdict(await caseVerdict(risk.case.case_id, use.trim(), "")); }
    catch { setErr("Verdict failed."); } finally { setVLoading(false); }
  }

  const s = sigOf(risk?.signal ?? "unknown");
  const selNode = sel && graph ? graph.nodes.find((n) => n.case_id === sel.citing_id) : null;

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <div className="mx-auto w-full max-w-6xl px-5 py-8">
        {/* search */}
        <form onSubmit={onSearch} className="flex gap-2">
          <input value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Is it still good law?  ·  case name or citation"
            className="flex-1 rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm outline-none placeholder:text-slate-500 focus:border-white/30" />
          <button disabled={loading || !query.trim()} className="rounded-full bg-white px-6 text-sm font-medium text-slate-900 transition hover:bg-slate-200 disabled:opacity-40">Check</button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          {DEMO.map((c) => (
            <button key={c.id} onClick={() => load(c.id)} disabled={loading}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300 transition hover:bg-white/10 disabled:opacity-40">{c.name}</button>
          ))}
        </div>
        {err && <p className="mt-5 text-sm text-red-400">{err}</p>}
        {loading && <p className="mt-5 text-sm text-slate-500">Loading dossier…</p>}

        {risk && !loading && (
          <div className="mt-6 space-y-5">
            {/* VERDICT HERO */}
            <Card className={`p-6 ring-1 ${s.ring} shadow-[0_0_60px_-20px] ${s.glow}`}>
              <div className="flex items-center gap-2">
                <span className={`h-2.5 w-2.5 rounded-full ${s.dot}`} />
                <span className={`text-sm font-semibold uppercase tracking-wide ${s.txt}`}>{s.label}</span>
                <span className="ml-auto text-xs text-slate-500">risk {risk.risk_score.toFixed(2)}</span>
              </div>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">{risk.case.case_name}</h1>
              <p className="text-sm text-slate-400">{[risk.case.citation, risk.case.court, risk.case.date_filed].filter(Boolean).join("  ·  ")}</p>
              {props?.operative_rule && (
                <p className="mt-4 border-l-2 border-white/20 pl-3 text-base font-medium leading-snug text-white">{props.operative_rule}</p>
              )}
              <p className="mt-3 text-sm text-slate-300">{risk.risk_rationale}</p>
              {risk.ground_truth.overruled_by && <p className="mt-2 text-xs font-medium text-red-400">Ground truth: overruled by {risk.ground_truth.overruled_by}</p>}
            </Card>

            {/* STATS BENTO */}
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
              <Card className="p-5">
                <H>Treatment mix</H>
                <div className="mt-3 flex gap-4 text-sm">
                  <span><span className="text-lg font-semibold text-red-400">{risk.negative_treatments.length}</span> <span className="text-slate-400">negative</span></span>
                  <span><span className="text-lg font-semibold text-green-400">{risk.positive_signal.approving_cites}</span> <span className="text-slate-400">approving</span></span>
                  <span><span className="text-lg font-semibold text-white">{risk.positive_signal.total_citing}</span> <span className="text-slate-400">citing</span></span>
                </div>
              </Card>
              <Card className="p-5"><H>Erosion over time</H><div className="mt-3">{<Sparkline trend={risk.trend} />}</div></Card>
              <Card className="p-5">
                <H>Analysis depth</H>
                {triage ? (
                  <>
                    <div className="mt-3 flex h-2.5 overflow-hidden rounded-full bg-white/10">
                      <div className="bg-emerald-500" style={{ width: `${(triage.counts.deep / triage.total) * 100}%` }} />
                      <div className="bg-yellow-400" style={{ width: `${(triage.counts.shallow / triage.total) * 100}%` }} />
                      <div className="bg-slate-500" style={{ width: `${(triage.counts.mention / triage.total) * 100}%` }} />
                    </div>
                    <p className="mt-2 text-xs text-slate-400">{triage.counts.deep} deep · {triage.counts.shallow} shallow · {triage.counts.mention} mention</p>
                  </>
                ) : <p className="mt-3 text-xs text-slate-500">—</p>}
              </Card>
            </div>

            {/* GRAPH + EVIDENCE */}
            {graph && (
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_340px]">
                <Card className="relative h-[600px] overflow-hidden">
                  <div className="absolute left-4 top-4 z-10 flex gap-2 text-xs">
                    <span className="rounded-full bg-white/5 px-3 py-1 ring-1 ring-white/10 text-slate-300">Citation graph</span>
                    <button onClick={() => setHideNeutral((v) => !v)}
                      className={`rounded-full px-3 py-1 ring-1 transition ${hideNeutral ? "bg-white/15 text-white ring-white/30" : "bg-white/5 text-slate-300 ring-white/10"}`}>
                      {hideNeutral ? "Treated only" : "All cites"}
                    </button>
                  </div>
                  <CitationGraph graph={graph} onSelect={setSel} hideNeutral={hideNeutral} />
                </Card>
                <Card className="p-5">
                  <H>Evidence</H>
                  {sel ? (
                    <div className="mt-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${sel.polarity === "negative" ? "bg-red-500/15 text-red-300 ring-red-500/40" : sel.polarity === "positive" ? "bg-green-500/15 text-green-300 ring-green-500/40" : "bg-slate-500/15 text-slate-300 ring-slate-500/30"}`}>
                          {sel.treatment ?? "neutral"}
                        </span>
                        <span className="text-xs text-slate-300">{selNode?.case_name}</span>
                      </div>
                      <p className="mt-1 text-[11px] text-slate-500">{[selNode?.court, selNode?.date_filed].filter(Boolean).join(" · ")}</p>
                      {sel.quote ? <blockquote className="mt-3 border-l-2 border-white/20 pl-3 text-xs italic text-slate-300">“{sel.quote}”</blockquote>
                        : <p className="mt-3 text-xs text-slate-500">Cited without a classified passage.</p>}
                      {sel.source_url && <a href={sel.source_url} target="_blank" rel="noreferrer" className="mt-3 inline-block text-xs text-sky-400 hover:text-sky-300">View source ↗</a>}
                    </div>
                  ) : <p className="mt-3 text-sm text-slate-500">Click any case in the graph to read the passage that grounds its treatment.</p>}
                </Card>
              </div>
            )}

            {/* PROPOSITIONS */}
            {props?.propositions?.length ? (
              <Card className="p-5">
                <H>How each holding held up</H>
                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {props.propositions.map((p) => {
                    const ps = sigOf(p.signal);
                    return (
                      <div key={p.proposition_id} className="rounded-xl border border-white/10 p-3">
                        <div className="flex items-center gap-2">
                          <span className={`h-1.5 w-1.5 rounded-full ${ps.dot}`} />
                          <span className="font-mono text-[11px] text-slate-400">{p.proposition_id}</span>
                          <span className="text-sm font-medium text-white">{p.label}</span>
                          <span className={`ml-auto text-[10px] uppercase ${ps.txt}`}>{p.status}</span>
                        </div>
                        {p.what_changed && <p className="mt-1.5 text-xs text-slate-400">{p.what_changed}</p>}
                      </div>
                    );
                  })}
                </div>
              </Card>
            ) : null}

            {/* TREATMENTS */}
            {risk.negative_treatments.length > 0 && (
              <Card className="p-5">
                <H>Negative treatments ({risk.negative_treatments.length})</H>
                <ul className="mt-3 space-y-3">
                  {risk.negative_treatments.map((t, i) => (
                    <li key={i} className="rounded-xl border border-white/10 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-[11px] font-medium text-red-300 ring-1 ring-red-500/40">{t.type}{t.on_other_grounds ? " · other grounds" : ""}</span>
                        <span className="text-xs text-slate-300">{t.citing_case.case_name}{t.citing_case.date_filed ? ` · ${t.citing_case.date_filed}` : ""}</span>
                        {t.confidence != null && <span className="ml-auto text-[11px] text-slate-500">{Math.round(t.confidence * 100)}%</span>}
                      </div>
                      {t.quote && <p className="mt-2 text-xs italic text-slate-400">“{t.quote}”</p>}
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {/* USE-AWARE VERDICT */}
            <Card className="border-dashed p-6">
              <H>Verdict for your use</H>
              <p className="mt-1 text-sm text-slate-400">Tell us the proposition you&apos;d cite it for — we judge the risk for that specific use.</p>
              <form onSubmit={getVerdict} className="mt-4 flex gap-2">
                <input value={use} onChange={(e) => setUse(e.target.value)}
                  placeholder={`e.g. cite ${(risk.case.case_name ?? "this").split(" ")[0]} for the public-carry right`}
                  className="flex-1 rounded-full border border-white/10 bg-white/5 px-4 py-2.5 text-sm outline-none placeholder:text-slate-500 focus:border-white/30" />
                <button disabled={vLoading || !use.trim()} className="rounded-full bg-white px-6 text-sm font-medium text-slate-900 transition hover:bg-slate-200 disabled:opacity-40">{vLoading ? "Judging…" : "Get verdict"}</button>
              </form>
              {verdict && (
                <div className="mt-5">
                  <div className={`flex items-center gap-2 ${verdict.real_risk ? "text-red-400" : "text-green-400"}`}>
                    <span className={`h-2.5 w-2.5 rounded-full ${verdict.real_risk ? "bg-red-500" : "bg-green-500"}`} />
                    <span className="text-sm font-semibold uppercase tracking-wide">{verdict.real_risk ? "Risky for this use" : "Safe for this use"}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-300">{verdict.risk_explanation}</p>
                  {verdict.close_to_overruled?.flag && <p className="mt-2 text-xs text-red-400">⚠ Close to overruled: {verdict.close_to_overruled.rationale}</p>}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {verdict.per_proposition.map((p) => (
                      <span key={p.proposition_id} className={`rounded-full px-2.5 py-1 text-[11px] ring-1 ${sigOf(p.signal).ring} ${sigOf(p.signal).txt}`}>
                        {p.proposition_id}{p.relevant_to_use ? " ●" : ""} · {p.signal}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          </div>
        )}
      </div>
    </main>
  );
}
