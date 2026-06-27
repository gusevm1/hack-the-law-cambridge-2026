"use client";

// Dev data-inspector: see exactly what's in the DB for a case and why — every
// inbound edge, its provenance (source/depth/tier), the stored passage, and the
// treatments classified from it (incl. UNCLASSIFIED edges, so recall gaps show).
// Backed by GET /cases/{id}/inspect.
import { useCallback, useEffect, useState } from "react";
import { caseInspect, type InspectEdge, type InspectResult } from "../../lib/api";

const DEMO: { name: string; id: number }[] = [
  { name: "Bruen", id: 6480696 },
  { name: "Roe", id: 108713 },
  { name: "Plessy", id: 94508 },
  { name: "Bowers", id: 111738 },
  { name: "Lochner", id: 96276 },
  { name: "Auer", id: 118089 },
  { name: "Smith", id: 112404 },
];

const POL_NEG = new Set(["overruled", "reversed", "abrogated", "criticised", "questioned", "limited"]);
const treatColor = (t: string | null) =>
  t && POL_NEG.has(t)
    ? "bg-red-500/15 text-red-300 ring-red-500/40"
    : t === "followed"
      ? "bg-green-500/15 text-green-300 ring-green-500/40"
      : "bg-slate-500/15 text-slate-300 ring-slate-500/30";

export default function Dev() {
  const [id, setId] = useState(6480696);
  const [input, setInput] = useState("6480696");
  const [data, setData] = useState<InspectResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<number | null>(null);

  const load = useCallback(async (caseId: number) => {
    setLoading(true);
    setError(null);
    setOpen(null);
    try {
      setData(await caseInspect(caseId));
    } catch {
      setError("Couldn't reach the API on :8080.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => void load(id), 0);
    return () => clearTimeout(t);
  }, [id, load]);

  return (
    <main className="min-h-screen bg-slate-950 px-5 py-6 font-mono text-[13px] text-slate-200">
      <div className="mx-auto w-full max-w-6xl">
        <h1 className="text-sm font-semibold text-white">citator · data inspector</h1>
        <p className="mt-1 text-xs text-slate-500">
          Raw rows from the DB for a target case — provenance, passages, and treatments.
        </p>

        {/* Picker */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {DEMO.map((c) => (
            <button
              key={c.id}
              onClick={() => setId(c.id)}
              className={`rounded px-2.5 py-1 text-xs ring-1 transition ${
                id === c.id
                  ? "bg-white text-slate-900 ring-white"
                  : "bg-white/5 text-slate-300 ring-white/10 hover:bg-white/10"
              }`}
            >
              {c.name}
            </button>
          ))}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const n = Number(input);
              if (n > 0) setId(n);
            }}
            className="ml-auto flex gap-1"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="cluster id"
              className="w-28 rounded bg-white/5 px-2 py-1 text-xs outline-none ring-1 ring-white/10 focus:ring-white/30"
            />
            <button className="rounded bg-white/10 px-2.5 py-1 text-xs hover:bg-white/20">
              load
            </button>
          </form>
        </div>

        {loading && <p className="mt-6 text-xs text-slate-500">loading…</p>}
        {error && <p className="mt-6 text-xs text-red-400">{error}</p>}

        {data && !loading && (
          <>
            {/* Target + counts */}
            <div className="mt-5 rounded-lg border border-white/10 bg-slate-900/60 p-4">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="text-sm font-semibold text-white">
                  {data.target.case_name ?? `case ${data.target.case_id}`}
                </span>
                <span className="text-xs text-slate-400">
                  {[data.target.citation, data.target.court, data.target.date_filed]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
                <span className="text-[11px] text-slate-600">
                  id {data.target.case_id} · source {data.target.source ?? "—"} ·{" "}
                  {data.target.in_db ? "in DB" : "NOT in DB"}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-3 text-xs">
                <Stat label="edges" value={data.counts.edges} />
                <Stat label="binding" value={data.counts.binding} />
                <Stat label="classified" value={data.counts.classified} />
                <Stat label="unclassified" value={data.counts.unclassified} warn={data.counts.unclassified > 0} />
                <Stat label="with passage" value={data.counts.with_passage} />
              </div>
            </div>

            {/* Edge table */}
            <div className="mt-4 overflow-hidden rounded-lg border border-white/10">
              <table className="w-full border-collapse text-left">
                <thead className="bg-white/5 text-[11px] uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">tier</th>
                    <th className="px-3 py-2 font-medium">citing case</th>
                    <th className="px-3 py-2 font-medium">date</th>
                    <th className="px-3 py-2 font-medium">source</th>
                    <th className="px-3 py-2 font-medium">depth</th>
                    <th className="px-3 py-2 font-medium">treatment</th>
                    <th className="px-3 py-2 font-medium">psg</th>
                  </tr>
                </thead>
                <tbody>
                  {data.edges.map((e) => (
                    <EdgeRow
                      key={e.citing_id}
                      e={e}
                      open={open === e.citing_id}
                      onToggle={() => setOpen(open === e.citing_id ? null : e.citing_id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </main>
  );
}

function Stat({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <span className="flex items-baseline gap-1">
      <span className={`text-sm font-semibold ${warn ? "text-amber-300" : "text-white"}`}>
        {value}
      </span>
      <span className="text-slate-500">{label}</span>
    </span>
  );
}

function EdgeRow({ e, open, onToggle }: { e: InspectEdge; open: boolean; onToggle: () => void }) {
  const binding = e.tier.startsWith("binding");
  return (
    <>
      <tr
        onClick={onToggle}
        className="cursor-pointer border-t border-white/5 align-top hover:bg-white/5"
      >
        <td className="px-3 py-2">
          <span className={`text-[11px] ${binding ? "text-sky-300" : "text-slate-500"}`}>
            {e.tier}
          </span>
        </td>
        <td className="px-3 py-2 text-slate-200">
          {e.case_name ?? `cluster ${e.citing_id}`}
          <span className="ml-1 text-[11px] text-slate-600">{e.citation ?? ""}</span>
        </td>
        <td className="px-3 py-2 text-slate-400">{e.date_filed ?? "—"}</td>
        <td className="px-3 py-2 text-slate-500">{e.source ?? "—"}</td>
        <td className="px-3 py-2 text-slate-500">{e.depth ?? "—"}</td>
        <td className="px-3 py-2">
          {e.treatments.length === 0 ? (
            <span className="text-[11px] text-slate-600">unclassified</span>
          ) : (
            <span className="flex flex-wrap gap-1">
              {e.treatments.map((t, i) => (
                <span
                  key={i}
                  className={`rounded px-1.5 py-0.5 text-[10px] ring-1 ${treatColor(t.type)}`}
                >
                  {t.type}
                  {t.confidence != null ? ` ${Math.round(t.confidence * 100)}%` : ""}
                </span>
              ))}
            </span>
          )}
        </td>
        <td className="px-3 py-2 text-slate-500">{e.has_passage ? e.passage_chars : "—"}</td>
      </tr>
      {open && (
        <tr className="border-t border-white/5 bg-slate-900/60">
          <td colSpan={7} className="px-4 py-3">
            {e.passage_preview ? (
              <blockquote className="border-l-2 border-white/20 pl-3 text-xs italic leading-relaxed text-slate-300">
                {e.passage_preview}
                {e.passage_chars > e.passage_preview.length ? " …" : ""}
              </blockquote>
            ) : (
              <p className="text-xs text-slate-600">no stored passage for this edge</p>
            )}
            {e.treatments.map((t, i) => (
              <div key={i} className="mt-2 text-[11px] text-slate-400">
                <span className="text-slate-200">{t.type}</span>
                {t.scope ? ` · ${t.scope}` : ""}
                {t.on_other_grounds ? " · on other grounds" : ""}
                {t.model ? ` · ${t.model}` : ""}
                {t.quote ? <span className="text-slate-500"> — “{t.quote}”</span> : null}
              </div>
            ))}
            {e.opinion_url && (
              <a
                href={e.opinion_url}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-block text-[11px] text-sky-400 hover:text-sky-300"
              >
                open on CourtListener ↗
              </a>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
