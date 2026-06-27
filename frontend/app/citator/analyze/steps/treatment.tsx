"use client";

// Treatment step (Feature 3 — deep per-case analyzer). Fetches GET /cases/{id}/analyze
// (public, no auth — app/src/htl/routes/analyze.py) and renders the deep read: each
// citing case's per-PROPOSITION findings, grouped by proposition. This supersedes
// Feature 2's /classify (snippet-only) — analysis_depth tells you which depth each
// case actually got (full-text vs snippet), and the verbatim quote is highlighted in
// the passage. Owns its own fetch + loading/error state; mounted only when the user
// reaches the step, so the slow model read isn't paid for until they look.
import { useEffect, useState } from "react";
import {
  caseAnalyze,
  type AnalyzeResult,
  type AnalyzedEdge,
  type PropositionFinding,
} from "@/lib/api";

const API_DOWN = "Couldn't reach the citator API — is `just dev-api` running?";

// Proposition spine (scope §4) — order + short labels for grouping.
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
const WHOLE = "—"; // whole-case / no single proposition

// Treatment tone by polarity — red (overruling), amber (limiting/doubting),
// emerald (approving), muted (neutral/distinguished).
const TREATMENT_TONE: Record<string, string> = {
  overruled: "bg-red-500/15 text-red-600 dark:text-red-400",
  reversed: "bg-red-500/15 text-red-600 dark:text-red-400",
  abrogated: "bg-red-500/15 text-red-600 dark:text-red-400",
  limited: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  criticised: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  questioned: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-400",
  followed: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  distinguished: "bg-black/[0.06] opacity-80 dark:bg-white/10",
  "cited-neutral": "bg-black/[0.06] opacity-70 dark:bg-white/10",
};

type Row = { edge: AnalyzedEdge; finding: PropositionFinding };

// Flatten (edge → findings) into per-proposition buckets: a case touching several
// propositions appears under each one it affects.
function groupByProposition(edges: AnalyzedEdge[]) {
  const groups: Record<string, Row[]> = {};
  for (const e of edges) {
    for (const f of e.findings) {
      const p = f.proposition ?? WHOLE;
      (groups[p] ??= []).push({ edge: e, finding: f });
    }
  }
  const ordered = [...PROP_ORDER.filter((p) => groups[p]), ...(groups[WHOLE] ? [WHOLE] : [])];
  return ordered.map((id) => ({
    id,
    label: id === WHOLE ? "Whole-case / no single proposition" : `${id} · ${PROP_LABELS[id] ?? ""}`,
    rows: groups[id],
  }));
}

export function TreatmentStep({ caseId }: { caseId: number }) {
  const [data, setData] = useState<AnalyzeResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    caseAnalyze(caseId)
      .then((r) => !cancelled && setData(r))
      .catch(() => !cancelled && setError(API_DOWN))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  if (loading)
    return <p className="text-sm opacity-50">Deep-reading the citing opinions… (a few seconds)</p>;
  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!data) return null;

  const groups = groupByProposition(data.edges);
  const fullText = data.edges.filter((e) => e.analysis_depth === "full-text").length;

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-black/10 p-6 dark:border-white/15">
        <h2 className="text-xs font-semibold uppercase tracking-wide opacity-60">
          Deep analysis — {data.analyzed} of {data.total} edges read, by proposition
        </h2>
        <p className="mt-2 text-sm opacity-70">
          The {data.counts.mention} <code>mention</code> edge
          {data.counts.mention === 1 ? "" : "s"} were filtered as noise and skipped — only the deep +
          shallow edges earn the model. {fullText > 0 ? `${fullText} read in full-text mode; the` : "Each"}{" "}
          rest fell back to the snippet (lower confidence). One case can touch several propositions —
          it appears under each it affects. Each label is schema-constrained and its quote verified
          verbatim against the source.
        </p>
      </div>

      {groups.map((g) => (
        <div key={g.id}>
          <h3 className="mb-2 text-sm font-semibold">{g.label}</h3>
          <ul className="space-y-3">
            {g.rows.map((row, i) => (
              <FindingCard key={`${g.id}-${i}`} edge={row.edge} finding={row.finding} />
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function FindingCard({ edge, finding }: { edge: AnalyzedEdge; finding: PropositionFinding }) {
  const cc = edge.citing_case;
  const tone = TREATMENT_TONE[finding.treatment] ?? "bg-black/[0.06] dark:bg-white/10";

  return (
    <li className="rounded-2xl border border-black/10 p-4 dark:border-white/10">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tone}`}>
          {finding.treatment}
        </span>
        <span className="rounded-full border border-black/15 px-2 py-0.5 text-[11px] opacity-70 dark:border-white/20">
          {finding.holding_vs_dicta}
        </span>
        {finding.attribution === "reported" ? (
          <span
            className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-400"
            title="echoing another opinion's treatment, not its own"
          >
            reported ⚠
          </span>
        ) : (
          <span className="rounded-full bg-black/5 px-2 py-0.5 text-[11px] opacity-60 dark:bg-white/10">
            self
          </span>
        )}
        <span
          className={`rounded-full px-2 py-0.5 text-[11px] ${
            edge.analysis_depth === "full-text"
              ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
              : "bg-black/5 opacity-60 dark:bg-white/10"
          }`}
          title="provenance of the read"
        >
          {edge.analysis_depth}
        </span>
        <span className="ml-auto text-[11px] opacity-50">
          {Math.round(finding.confidence * 100)}% conf
        </span>
      </div>

      <p className="mt-2 text-sm font-medium">
        {cc.case_name ?? "Unknown citing case"}
        <span className="ml-2 text-xs font-normal opacity-60">
          {[cc.court, cc.date_filed, edge.citation].filter(Boolean).join("  ·  ")}
        </span>
      </p>

      {finding.what_changed && (
        <p className="mt-1 text-sm opacity-80">{finding.what_changed}</p>
      )}

      {finding.quote && (
        <p className="mt-2 text-xs italic opacity-80">
          “<HighlightedPassage passage={edge.passage} quote={finding.quote} />”
        </p>
      )}
      <p className="mt-1 text-[10px] uppercase tracking-wide opacity-40">
        {edge.tier} · {edge.source} · {edge.model}
      </p>
    </li>
  );
}

// The quote is verified verbatim backend-side; mark it where it appears. For full-
// text findings the quote comes from the full opinion, which may not be in the
// snippet `passage` shown here — fall back to the plain passage when it isn't.
function HighlightedPassage({ passage, quote }: { passage: string; quote: string }) {
  const i = quote ? passage.indexOf(quote) : -1;
  if (i < 0) return <>{passage}</>;
  return (
    <>
      {passage.slice(0, i)}
      <mark className="rounded bg-yellow-300/50 px-0.5 not-italic dark:bg-yellow-300/30">
        {quote}
      </mark>
      {passage.slice(i + quote.length)}
    </>
  );
}
