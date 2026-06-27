"use client";

// Citator analysis stepper. Fetches GET /cases/{id}/triage (public, no auth — see
// app/src/htl/routes/triage.py), which carries the resolved case + every inbound
// edge tiered deep|shallow|mention. Resolve, Citations, Treatment (the deep
// per-case read, Feature 3) and Relation (per-proposition evolution + risk,
// Feature 4) are live; Verdict is a placeholder for Feature 5. Defaults to Bruen
// (6480696). The case shown comes from the triage
// response itself, so this never depends on the live /resolve or the DB.
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  caseTriage,
  casePropositions,
  type TriageResult,
  type TieredEdge,
  type PropositionsResult,
} from "@/lib/api";
import VerdictStep from "./steps/verdict";
import { TreatmentStep } from "./steps/treatment";
import { RelationStep } from "./steps/relation";

const BRUEN_ID = 6480696;
const API_DOWN = "Couldn't reach the citator API — is `just dev-api` running?";

const STEPS = ["Resolve", "Citations", "Treatment", "Relation", "Verdict"] as const;

const TIER: Record<string, { dot: string; label: string; note: string }> = {
  deep: { dot: "bg-emerald-500", label: "Deep", note: "full analysis" },
  shallow: { dot: "bg-yellow-400", label: "Shallow", note: "light pass" },
  mention: { dot: "bg-gray-400", label: "Mention", note: "surfaced, low-ranked" },
};

// Proposition spine (scope §4). Order + short labels for grouping.
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

export default function Analyze() {
  const [step, setStep] = useState(0);
  const [idInput, setIdInput] = useState(String(BRUEN_ID));
  const [data, setData] = useState<TriageResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [props, setProps] = useState<PropositionsResult | null>(null);
  const [propsLoading, setPropsLoading] = useState(false);
  const [propsError, setPropsError] = useState<string | null>(null);

  async function load(id: number) {
    setLoading(true);
    setError(null);
    setProps(null); // stale aggregation belongs to the previous case
    try {
      setData(await caseTriage(id));
    } catch {
      setError(API_DOWN);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(BRUEN_ID);
  }, []);

  // Lazily aggregate propositions when the user reaches the Relation step — the
  // backend read is slow, so don't pay for it until they look. (The Treatment step
  // self-fetches /analyze on mount.)
  useEffect(() => {
    if (step !== 3 || !data) return;
    if (props && props.case.case_id === data.case.case_id) return;
    let cancelled = false;
    setPropsLoading(true);
    setPropsError(null);
    casePropositions(data.case.case_id)
      .then((r) => !cancelled && setProps(r))
      .catch(() => !cancelled && setPropsError(API_DOWN))
      .finally(() => !cancelled && setPropsLoading(false));
    return () => {
      cancelled = true;
    };
  }, [step, data, props]);

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-lg font-semibold">Citator — proposition-level analysis</h1>
        <p className="text-xs opacity-60">
          The pipeline, step by step. Stage 1 (Filter) tiers every inbound citation by
          how much analysis it earns — nothing is dropped.{" "}
          <Link href="/citator" className="underline underline-offset-2 hover:opacity-80">
            ← Back to the citator
          </Link>
        </p>
      </header>

      {/* Stepper */}
      <nav className="mb-6 flex flex-wrap gap-2">
        {STEPS.map((label, i) => {
          const done = i < step;
          const active = i === step;
          return (
            <button
              key={label}
              type="button"
              onClick={() => setStep(i)}
              className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                active
                  ? "border-foreground bg-foreground text-background"
                  : done
                    ? "border-black/30 dark:border-white/40"
                    : "border-black/15 opacity-60 dark:border-white/20"
              }`}
            >
              {i + 1}. {label}
            </button>
          );
        })}
      </nav>

      {/* Case loader */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const id = Number(idInput);
          if (Number.isFinite(id)) load(id);
        }}
        className="mb-6 flex gap-2"
      >
        <input
          value={idInput}
          onChange={(e) => setIdInput(e.target.value)}
          inputMode="numeric"
          className="w-40 rounded-full border border-black/15 bg-transparent px-4 py-2 text-sm outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50"
          aria-label="CourtListener cluster id"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-full border border-black/15 px-4 py-2 text-sm transition-colors hover:bg-black/5 disabled:opacity-40 dark:border-white/20 dark:hover:bg-white/10"
        >
          Load
        </button>
        <span className="self-center text-xs opacity-50">default: Bruen 6480696</span>
      </form>

      {loading && <p className="text-sm opacity-50">Loading triage…</p>}
      {error && <p className="text-sm text-red-500">{error}</p>}

      {data && !loading && (
        <>
          {step === 0 && <ResolveStep data={data} />}
          {step === 1 && <CitationsStep data={data} />}
          {step === 2 && <TreatmentStep caseId={data.case.case_id} />}
          {step === 3 && (
            <RelationStep data={props} loading={propsLoading} error={propsError} />
          )}
          {step === 4 && <VerdictStep caseId={data.case.case_id} active={step === 4} />}

          {/* Nav */}
          <div className="mt-8 flex justify-between">
            <button
              type="button"
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              disabled={step === 0}
              className="rounded-full border border-black/15 px-4 py-2 text-sm disabled:opacity-30 dark:border-white/20"
            >
              ← Back
            </button>
            <button
              type="button"
              onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
              disabled={step === STEPS.length - 1}
              className="rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background disabled:opacity-30"
            >
              Next →
            </button>
          </div>
        </>
      )}
    </main>
  );
}

function ResolveStep({ data }: { data: TriageResult }) {
  const c = data.case;
  return (
    <section className="rounded-3xl border border-black/10 p-6 dark:border-white/15">
      <h2 className="text-xs font-semibold uppercase tracking-wide opacity-60">Resolved target</h2>
      <p className="mt-2 text-base font-semibold">{c.case_name ?? `Case ${c.case_id}`}</p>
      <p className="text-xs opacity-60">
        {[c.citation, c.court, c.date_filed].filter(Boolean).join("  ·  ") || "No metadata"}
      </p>
      <p className="mt-4 text-sm opacity-70">
        {data.total} inbound citation{data.total === 1 ? "" : "s"} retrieved (full-text ∪ graph).
        Next: the filter tiers them by depth of analysis.
      </p>
    </section>
  );
}

function CitationsStep({ data }: { data: TriageResult }) {
  const { counts, total } = data;
  const groups = groupByProposition(data.edges);
  const pct = (n: number) => (total ? (n / total) * 100 : 0);

  return (
    <section className="space-y-6">
      {/* Funnel */}
      <div className="rounded-3xl border border-black/10 p-6 dark:border-white/15">
        <h2 className="text-xs font-semibold uppercase tracking-wide opacity-60">
          The funnel — {total} citations, nothing dropped
        </h2>
        <div className="mt-3 flex h-3 w-full overflow-hidden rounded-full bg-black/5 dark:bg-white/10">
          <div className="bg-emerald-500" style={{ width: `${pct(counts.deep)}%` }} />
          <div className="bg-yellow-400" style={{ width: `${pct(counts.shallow)}%` }} />
          <div className="bg-gray-400" style={{ width: `${pct(counts.mention)}%` }} />
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-xs">
          {(["deep", "shallow", "mention"] as const).map((t) => (
            <span key={t} className="flex items-center gap-1.5">
              <span className={`inline-block h-2.5 w-2.5 rounded-full ${TIER[t].dot}`} />
              <span className="font-medium capitalize">{t}</span>
              <span className="tabular-nums opacity-60">{counts[t]}</span>
              <span className="opacity-40">· {TIER[t].note}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Grouped by proposition */}
      {groups.map((g) => (
        <div key={g.id}>
          <h3 className="mb-2 text-sm font-semibold">{g.label}</h3>
          <ul className="space-y-3">
            {g.edges.map((e, i) => (
              <EdgeCard key={`${g.id}-${i}`} edge={e} />
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function EdgeCard({ edge }: { edge: TieredEdge }) {
  const tier = TIER[edge.tier] ?? TIER.mention;
  const cc = edge.citing_case;
  return (
    <li className="rounded-2xl border border-black/10 p-4 dark:border-white/10">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 rounded-full bg-black/5 px-2 py-0.5 text-[11px] font-medium dark:bg-white/10">
          <span className={`inline-block h-2 w-2 rounded-full ${tier.dot}`} />
          {tier.label}
        </span>
        <span className="text-sm font-medium">{cc.case_name ?? "Unknown citing case"}</span>
        <span className="text-xs opacity-60">
          {[cc.court, cc.date_filed, edge.citation].filter(Boolean).join("  ·  ")}
        </span>
        <span className="ml-auto flex items-center gap-2 text-[11px] opacity-60">
          <span className="rounded-full border border-black/15 px-1.5 py-0.5 dark:border-white/20">
            {edge.source}
          </span>
          {edge.matched_citation && <span>matched {edge.matched_citation}</span>}
          {edge.opinion_url && (
            <a
              href={edge.opinion_url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2 hover:opacity-100"
            >
              opinion →
            </a>
          )}
        </span>
      </div>

      <p className="mt-2 text-xs italic opacity-80">“{edge.passage}”</p>

      {edge.reasons.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {edge.reasons.map((r, i) => (
            <li
              key={i}
              className="rounded-full bg-black/[0.04] px-2 py-0.5 text-[11px] opacity-70 dark:bg-white/[0.06]"
            >
              {r}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
