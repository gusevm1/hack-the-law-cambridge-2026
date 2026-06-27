// Static overview / showcase of the open-citator build. No data fetching — it
// links into the live surfaces (/citator graph, /assistant). Public.
import Link from "next/link";

export const metadata = {
  title: "Open Citator — overview",
  description: "Is this authority still good law? A grounded, open citator.",
};

const SIGNALS = [
  {
    dot: "bg-red-500",
    ring: "ring-red-500/30",
    label: "No longer good law",
    desc: "A higher court overruled it, or a statute superseded it.",
    eg: "Roe v. Wade → Dobbs (2022)",
  },
  {
    dot: "bg-amber-400",
    ring: "ring-amber-400/30",
    label: "Good, but eroding",
    desc: "Still standing, yet narrowed, distinguished, or partly overruled.",
    eg: "NYSRPA v. Bruen → narrowed by Rahimi (2024)",
  },
  {
    dot: "bg-green-500",
    ring: "ring-green-500/30",
    label: "Still good law",
    desc: "No negative treatment found — followed, with the evidence to prove it.",
    eg: "Auer v. Robbins — followed, not overruled",
  },
];

const FEATURES = [
  {
    title: "Resolve",
    body: "A citation or case name → the canonical case. A found:false gate means we never invent an authority.",
  },
  {
    title: "Verdict — and the why",
    body: "A red/amber/green signal with a plain-English rationale, grounded in the later authorities that treated it.",
  },
  {
    title: "Treatment graph",
    body: "The citation network: every citer around the focal case, edges coloured by how they treat it. Click any edge to read the passage and follow it to the source opinion.",
  },
  {
    title: "Grounded retrieval",
    body: "Real CourtListener data. Reporter-format-agnostic graph search, revision-duplicate dedup, and binding-tier-exhaustive recall (SCOTUS + circuits in full).",
  },
];

const DEMO = [
  { name: "NYSRPA v. Bruen", id: 6480696, sig: "green", note: "eroding" },
  { name: "Roe v. Wade", id: 108713, sig: "red", note: "overruled · Dobbs" },
  { name: "Plessy v. Ferguson", id: 94508, sig: "red", note: "overruled · Brown" },
  { name: "Bowers v. Hardwick", id: 111738, sig: "red", note: "overruled · Lawrence" },
  { name: "Lochner v. New York", id: 96276, sig: "red", note: "overruled · W. Coast Hotel" },
  { name: "Auer v. Robbins", id: 118089, sig: "green", note: "good law" },
];

const DOT: Record<string, string> = {
  red: "bg-red-500",
  amber: "bg-amber-400",
  green: "bg-green-500",
};

const PIPELINE = [
  ["Resolve", "citation / name → canonical case"],
  ["Retrieve", "CourtListener graph · dedup · recall"],
  ["Classify", "passages → treatment (Gemini)"],
  ["Verdict + Graph", "signal · why · network"],
];

export default function Overview() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <div className="mx-auto w-full max-w-6xl px-6 py-14">
        {/* Hero */}
        <section className="text-center">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
            Hack the Law · Clio challenge
          </p>
          <h1 className="mt-3 bg-gradient-to-r from-white via-slate-200 to-slate-500 bg-clip-text text-4xl font-semibold tracking-tight text-transparent sm:text-5xl">
            Is this authority still good law?
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-slate-400">
            An open citator. A 2010 judgment reads the same whether or not it was
            overruled in 2021 — the signal lives in the network of cases that came
            after it. We reconstruct that network, and tell you the answer with the
            evidence to back it.
          </p>
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/citator"
              className="rounded-full bg-white px-6 py-2.5 text-sm font-medium text-slate-900 transition hover:bg-slate-200"
            >
              Open the live graph →
            </Link>
            <Link
              href="/assistant"
              className="rounded-full border border-white/15 px-6 py-2.5 text-sm font-medium text-slate-200 transition hover:bg-white/5"
            >
              Try the assistant
            </Link>
          </div>
        </section>

        {/* The three signals */}
        <section className="mt-16 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {SIGNALS.map((s) => (
            <div
              key={s.label}
              className={`rounded-2xl border border-white/10 bg-slate-900/50 p-5 ring-1 ${s.ring}`}
            >
              <div className="flex items-center gap-2">
                <span className={`h-2.5 w-2.5 rounded-full ${s.dot}`} />
                <span className="text-sm font-semibold">{s.label}</span>
              </div>
              <p className="mt-2 text-sm text-slate-400">{s.desc}</p>
              <p className="mt-3 text-xs text-slate-500">{s.eg}</p>
            </div>
          ))}
        </section>

        {/* What it does */}
        <section className="mt-14">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">
            What it does
          </h2>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border border-white/10 bg-slate-900/50 p-5"
              >
                <h3 className="text-sm font-semibold text-white">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Pipeline */}
        <section className="mt-14">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">
            How it works
          </h2>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-stretch">
            {PIPELINE.map((step, i) => (
              <div key={step[0]} className="flex flex-1 items-center gap-3">
                <div className="flex-1 rounded-xl border border-white/10 bg-slate-900/50 p-4">
                  <p className="text-sm font-semibold text-white">{step[0]}</p>
                  <p className="mt-1 text-xs text-slate-400">{step[1]}</p>
                </div>
                {i < PIPELINE.length - 1 && (
                  <span className="hidden text-slate-600 sm:block">→</span>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Demo gallery */}
        <section className="mt-14">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">
            Worked examples — click to open the network
          </h2>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {DEMO.map((c) => (
              <Link
                key={c.id}
                href={`/citator?case=${c.id}`}
                className="group rounded-2xl border border-white/10 bg-slate-900/50 p-4 transition hover:border-white/25 hover:bg-slate-900"
              >
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${DOT[c.sig]}`} />
                  <span className="text-sm font-medium text-white group-hover:underline">
                    {c.name}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{c.note}</p>
              </Link>
            ))}
          </div>
        </section>

        <footer className="mt-16 border-t border-white/10 pt-6 text-center text-xs text-slate-500">
          Built on CourtListener (Free Law Project) public data. General information,
          not legal advice.
        </footer>
      </div>
    </main>
  );
}
