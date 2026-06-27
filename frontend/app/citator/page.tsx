"use client";

// Public citator page — POST /resolve {query} → GET /cases/{id}/risk, both
// unauthenticated (see app/src/htl/routes/resolve.py · risk.py). No global auth
// middleware, so this route is public by default, matching the endpoints.
import { useState } from "react";
import { resolve, caseRisk, type RiskResult } from "../../lib/api";
import { VerdictCard } from "../../components/verdict-card";

// The 6 seeded demo cases — one click loads risk by id, skipping /resolve.
const DEMO: { name: string; id: number }[] = [
  { name: "Roe v. Wade", id: 108713 },
  { name: "Plessy v. Ferguson", id: 94508 },
  { name: "Bowers v. Hardwick", id: 111738 },
  { name: "Lochner v. New York", id: 96276 },
  { name: "Auer v. Robbins", id: 118089 },
  { name: "Emp. Division v. Smith", id: 112404 },
];

const API_DOWN = "Couldn't reach the citator API — is `just dev-api` running?";

export default function Citator() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [risk, setRisk] = useState<RiskResult | null>(null);

  function reset() {
    setError(null);
    setNotFound(null);
    setNote(null);
  }

  async function loadRisk(id: number) {
    reset();
    setLoading(true);
    try {
      setRisk(await caseRisk(id));
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
      const data = await resolve(q);
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

      {risk && !loading && <VerdictCard risk={risk} note={note} />}
    </main>
  );
}
