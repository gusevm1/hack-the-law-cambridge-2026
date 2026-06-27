"use client";

// Public citator page — POST /resolve {query} → GET /cases/{id}/risk, both
// unauthenticated (see app/src/htl/routes/resolve.py · risk.py). No global auth
// middleware, so this route is public by default, matching the endpoints.
import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

type ResolveResponse = {
  found: boolean;
  case_id: number | null;
  case_name: string | null;
  citation: string | null;
  court: string | null;
  date_filed: string | null;
  source: string | null;
  ambiguous: boolean;
};

type TrendPoint = { year: number; neg: number; pos: number; neg_share: number };
type CitingCaseRef = {
  case_name: string | null;
  court: string | null;
  date_filed: string | null;
};
type NegativeTreatment = {
  citing_case: CitingCaseRef;
  type: string;
  scope: string | null;
  on_other_grounds: boolean;
  quote: string | null;
  confidence: number | null;
};
type CaseRef = {
  case_id: number;
  case_name: string | null;
  citation: string | null;
  court: string | null;
  date_filed: string | null;
};
type RiskResponse = {
  case: CaseRef;
  as_of: string;
  signal: string;
  status: string;
  risk_score: number;
  risk_rationale: string;
  trend: TrendPoint[];
  negative_treatments: NegativeTreatment[];
  positive_signal: { approving_cites: number; total_citing: number };
  ground_truth: { on_loc_overruled_list: boolean; overruled_by: string | null };
};

// The 6 seeded demo cases — one click loads risk by id, skipping /resolve.
const DEMO: { name: string; id: number }[] = [
  { name: "Roe v. Wade", id: 108713 },
  { name: "Plessy v. Ferguson", id: 94508 },
  { name: "Bowers v. Hardwick", id: 111738 },
  { name: "Lochner v. New York", id: 96276 },
  { name: "Auer v. Robbins", id: 118089 },
  { name: "Emp. Division v. Smith", id: 112404 },
];

const SIGNAL: Record<string, { dot: string; label: string }> = {
  red: { dot: "bg-red-500", label: "High risk" },
  amber: { dot: "bg-yellow-400", label: "Eroding" },
  green: { dot: "bg-green-500", label: "Good law" },
  unknown: { dot: "bg-gray-400", label: "Unknown" },
};

const API_DOWN = "Couldn't reach the citator API — is `just dev-api` running?";

export default function Citator() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [risk, setRisk] = useState<RiskResponse | null>(null);

  function reset() {
    setError(null);
    setNotFound(null);
    setNote(null);
  }

  async function loadRisk(id: number) {
    reset();
    setLoading(true);
    try {
      const res = await fetch(`${API}/cases/${id}/risk`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      setRisk((await res.json()) as RiskResponse);
    } catch {
      setError(API_DOWN);
      setRisk(null);
    } finally {
      setLoading(false);
    }
  }

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q || loading) return;
    reset();
    setLoading(true);
    try {
      const res = await fetch(`${API}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = (await res.json()) as ResolveResponse;
      if (!data.found || data.case_id == null) {
        setRisk(null);
        setNotFound(`No such case found for “${q}”.`);
        return;
      }
      if (data.ambiguous) setNote("Multiple matches — showing the top hit.");
      await loadRisk(data.case_id);
    } catch {
      setError(API_DOWN);
      setRisk(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-lg font-semibold">Citator — is it still good law?</h1>
        <p className="text-xs opacity-60">
          Look up a case by citation or name and see its erosion signal. General
          information, not legal advice.
        </p>
      </header>

      <form onSubmit={onSearch} className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. Roe v. Wade  ·  410 U.S. 113"
          className="flex-1 rounded-full border border-black/15 bg-transparent px-4 py-2 text-sm outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background disabled:opacity-40"
        >
          Check
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {DEMO.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => loadRisk(c.id)}
            disabled={loading}
            className="rounded-full border border-black/15 px-3 py-1 text-xs transition-colors hover:bg-black/5 disabled:opacity-40 dark:border-white/20 dark:hover:bg-white/10"
          >
            {c.name}
          </button>
        ))}
      </div>

      {loading && <p className="mt-6 text-sm opacity-50">Checking…</p>}
      {error && <p className="mt-6 text-sm text-red-500">{error}</p>}
      {notFound && !loading && (
        <p className="mt-6 text-sm opacity-70">{notFound}</p>
      )}

      {risk && !loading && <Verdict risk={risk} note={note} />}
    </main>
  );
}

function Verdict({ risk, note }: { risk: RiskResponse; note: string | null }) {
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
