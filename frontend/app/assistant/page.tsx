"use client";

// Public agentic assistant — POST /ask {case, use} runs a citator-aware Gemini
// function-calling loop server-side (see app/src/htl/routes/ask.py) and returns
// a grounded prose answer plus the *verified* resolve + risk objects. The card
// renders from that real verdict, never from the prose. No auth, like /citator.
import { useState } from "react";
import Link from "next/link";
import { ask, type AskResult } from "../../lib/api";
import { VerdictCard } from "../../components/verdict-card";

// How the litigator intends to use the case — value === label is fine.
const USES = [
  "Cite as binding/controlling precedent",
  "Cite as persuasive authority",
  "Rely on its holding / rule",
  "Apply a test or standard it established",
  "Distinguish it from my facts",
  "Quote its reasoning / dicta",
];

const API_DOWN = "Couldn't reach the assistant API — is `just dev-api` running?";

export default function Assistant() {
  const [caseText, setCaseText] = useState("");
  const [use, setUse] = useState(USES[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResult | null>(null);

  async function onAsk(e: React.FormEvent) {
    e.preventDefault();
    const c = caseText.trim();
    if (!c || loading) return;
    setError(null);
    setLoading(true);
    try {
      setResult(await ask(c, use));
    } catch {
      setError(API_DOWN);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const resolved = result?.resolved_case ?? null;
  const verified = resolved?.found && resolved.case_id != null;

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-lg font-semibold">
          Legal assistant — can I still rely on this case?
        </h1>
        <p className="text-xs opacity-60">
          General information, not legal advice.{" "}
          <Link href="/citator" className="underline underline-offset-2 hover:opacity-80">
            Open the citator →
          </Link>
        </p>
      </header>

      <form onSubmit={onAsk} className="space-y-3">
        <input
          value={caseText}
          onChange={(e) => setCaseText(e.target.value)}
          placeholder="e.g. Roe v. Wade  ·  410 U.S. 113"
          className="w-full rounded-full border border-black/15 bg-transparent px-4 py-2 text-sm outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50"
        />
        <div className="flex flex-col gap-2 sm:flex-row">
          <label className="flex-1">
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
          <button
            type="submit"
            disabled={loading || !caseText.trim()}
            className="self-end rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background disabled:opacity-40"
          >
            Ask
          </button>
        </div>
      </form>

      {loading && (
        <p className="mt-6 text-sm opacity-50">Researching the citator…</p>
      )}
      {error && <p className="mt-6 text-sm text-red-500">{error}</p>}

      {result && !loading && (
        <section className="mt-6">
          {/* Grounded prose answer */}
          <div className="whitespace-pre-wrap rounded-3xl border border-black/10 bg-black/[0.02] p-6 text-sm leading-relaxed dark:border-white/15 dark:bg-white/[0.03]">
            {result.answer}
          </div>

          {/* Verified verdict card + source link, or a can't-verify note. */}
          {verified && result.verdict ? (
            <>
              <VerdictCard risk={result.verdict} />
              <p className="mt-4 text-xs opacity-70">
                <a
                  href={`https://www.courtlistener.com/opinion/${resolved!.case_id}/x/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline underline-offset-2 hover:opacity-100"
                >
                  View on CourtListener →
                </a>
                {resolved!.citation ? `  ·  ${resolved!.citation}` : ""}
              </p>
            </>
          ) : (
            <p className="mt-4 text-sm opacity-70">Couldn&apos;t verify that case.</p>
          )}
        </section>
      )}
    </main>
  );
}
