// LOCAL ONLY: pitch deck at /pptx. Not committed, not deployed. Scroll-snap slides
// designed to be screenshotted one-per-viewport from localhost:3000/pptx.
import Image from "next/image";

const BG = "bg-[linear-gradient(140deg,#2a2a2a_0%,#161616_45%,#0a0a0a_100%)]";

function SlideTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-8 text-center text-5xl font-extrabold tracking-tight text-white drop-shadow-sm">
      {children}
    </h2>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`w-full max-w-5xl rounded-[28px] bg-white p-10 shadow-2xl shadow-black/25 md:p-14 ${className}`}>
      {children}
    </div>
  );
}

// highlighter-marker emphasis for key words on the white cards
const Hi = ({ children }: { children: React.ReactNode }) => (
  <span className="rounded-md bg-amber-100/40 px-1.5 py-0.5 box-decoration-clone">{children}</span>
);

const Kicker = ({ children }: { children: React.ReactNode }) => (
  <p className="text-sm font-bold uppercase tracking-[0.18em] text-slate-400">{children}</p>
);

const cases = [
  { name: "Heller", year: "2008", note: "expansive individual right to bear arms for self-defence." },
  { name: "Bruen", year: "2022", note: "a regulation survives only with a historical twin: a hard bar." },
  { name: "Rahimi", year: "2024", note: "loosened. No twin needed, just a relevantly similar principle." },
  { name: "Hemani & Wolford", year: "2026", note: "recalibrated. The analogue must match on the why, not just the how." },
];

const unique = [
  { h: "Proposition-level, not case-level", b: "We split a case into its individual holdings and track each one separately. The same case can be green for one argument and red for another." },
  { h: "Direction of travel", b: "We show whether a rule is being reinforced or eroded, and by which courts, not just whether it has survived." },
  { h: "Grounded, never generated", b: "Every verdict traces back to a real citing passage. No confident-but-hallucinated good-law claims." },
  { h: "Use-aware", b: "Tell us the proposition you'd cite it for, and we judge the risk for that exact use, not in the abstract." },
];

const team = [
  { name: "Samuel Bartlett", bullets: ["Research in AI / new tech & MedTech at leading universities", "Lead for AI implementations at a 30,000-person company", "Entering the Swiss spacetech competition"] },
  { name: "Maxim Gusev", bullets: ["GenAI & GCP Challenge winner, HackTheLaw 2025", "Shipped a project with 5,000+ monthly users", "AI consultant for Artifact (AI boutique); active researcher"] },
  { name: "Pruthvirajsinh Zala", bullets: ["LLM Candidate, Wolfson College, Cambridge", "Former Judicial Clerk to the Chief Justice of India", "Bar Call (2023), licensed to practice law in India"] },
  { name: "Stefanos Palyvos", bullets: ["Aetheron: drone tech for autonomous reforestation", "Deliberate: multi-agent jury simulation for trial lawyers", "AI drone photogrammetry & swarm-intelligence researcher; incoming MAE, NYU Tandon"] },
];

const impact = [
  { big: "Hours → seconds", sub: "A good-law check means reading every citing case by hand. We do it on the spot." },
  { big: "Case → argument", sub: "An answer per holding, not one binary flag. Green for one use, red for another." },
  { big: "Grounded by default", sub: "Every verdict cites a verbatim passage: the guardrail legal AI is missing." },
];

// The "How it works" flow diagram. Nodes are positioned in a 1000x560 coordinate
// space (x,y = node CENTRE); the SVG edges below share that space so the bezier
// connectors line up exactly. `service` = an external call, `gemini` = AI applied here.
const flowNodes = [
  // row 1: aggregate every citing case, then narrow the candidate set
  { id: "query", x: 100, y: 95, kicker: "INPUT", title: "Lawyer's query", desc: "a case + the proposition you'd actually cite it for" },
  { id: "resolve", x: 300, y: 95, kicker: "RESOLVE", title: "Resolve on CourtListener", desc: "case name or cite to a canonical opinion id" },
  { id: "multihop", x: 500, y: 95, kicker: "RETRIEVE", title: "Multi-hop traversal", desc: "walk the citation graph to aggregate every citing case" },
  { id: "triage", x: 700, y: 95, kicker: "FILTER", title: "Depth triage", desc: "tier each cite deep / shallow / mention. nothing dropped" },
  { id: "sentiment", x: 900, y: 95, kicker: "CLASSIFY", title: "Sentiment + treatment", desc: "score each passage, keep the relevant ones, drop neutral noise", gemini: "3.5 Flash" },
  // row 2: read the survivors deeply, then compile what is actually affected
  { id: "analyze", x: 100, y: 300, kicker: "ANALYSE", title: "Deep full-text read", desc: "read each chosen opinion in full against the proposition spine", gemini: "3.1 Pro" },
  { id: "findings", x: 300, y: 300, kicker: "INTERMEDIATE", title: "Per-passage findings", desc: "treatment, holding (P1-P8), dicta vs holding, verbatim quote", intermediate: true, gemini: "3.1 Pro" },
  { id: "compile", x: 500, y: 300, kicker: "COMPILE", title: "Affected propositions", desc: "which gun-law holdings of the target are hit, signed risk + evolution", gemini: "3.5 Flash" },
  { id: "verdict", x: 720, y: 240, kicker: "OUTPUT", title: "Use-aware verdict", desc: "your use matched to compromised holdings, real risk for that use", gemini: "3.5 Flash" },
  { id: "chat", x: 720, y: 360, kicker: "OUTPUT", title: "Grounded chat", desc: "agentic Q&A over the proposition graph", gemini: "2.5 Pro" },
];

// Bezier edges in the same 1000x440 space. The long curve is the row-1 to row-2 wrap.
// Straight arrows run from under the source card to just short of the target card,
// so the cards (rendered on top) hide the slack at any container width.
const flowEdges = [
  { d: "M150 95 L214 95" },
  { d: "M350 95 L414 95" },
  { d: "M550 95 L614 95", label: "N candidates", lx: 600, ly: 82 },
  { d: "M750 95 L814 95" },
  { d: "M900 140 C 900 205 100 205 100 258", label: "relevant cases only", lx: 500, ly: 197 },
  { d: "M150 300 L214 300" },
  { d: "M350 300 L414 300", label: "findings", lx: 400, ly: 287 },
  { d: "M540 300 C 615 300 615 240 648 240" },
  { d: "M540 300 C 615 300 615 360 648 360" },
];

export default function Pptx() {
  return (
    <main className={`h-screen w-full snap-y snap-mandatory overflow-y-scroll scroll-smooth ${BG}`}>
      {/* ─────────────────────────── 1 · TITLE ─────────────────────────── */}
      <section className="relative flex min-h-screen snap-start flex-col items-center justify-center px-6 text-center">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{ backgroundImage: "linear-gradient(white 1px,transparent 1px),linear-gradient(90deg,white 1px,transparent 1px)", backgroundSize: "54px 54px" }}
        />
        <div className="relative flex flex-col items-center">
          <Image src="/logo.png" alt="CiteMeRight" width={132} height={132} priority className="rounded-3xl shadow-2xl shadow-black/30 ring-1 ring-white/25" />
          <h1 className="mt-8 text-7xl font-extrabold tracking-tight text-white">CiteMeRight</h1>
          <p className="mt-4 text-2xl font-medium text-white/80">Is it still good law?</p>
          <p className="mt-8 max-w-2xl text-lg leading-relaxed text-white/70">
            Beyond binary citators. We read the citation graph and tell you not just whether a case
            survives, but how far you can rely on it, and why.
          </p>
          <span className="mt-10 rounded-full border border-white/30 px-5 py-2 text-sm font-medium text-white/80">
            HackTheLaw · Cambridge 2026
          </span>
        </div>
        <span className="absolute bottom-8 animate-pulse text-sm text-white/60">scroll ↓</span>
      </section>

      {/* ─────────────────────────── 2 · PROBLEM ─────────────────────────── */}
      <section className="flex min-h-screen snap-start flex-col items-center justify-center px-6 py-16">
        <SlideTitle>The Problem</SlideTitle>
        <Card>
          <Kicker>The good-law gap</Kicker>
          <p className="mt-4 text-3xl font-bold leading-tight text-slate-900">
            A case is never simply <Hi>“good”</Hi> or <Hi>“bad”</Hi> law.
          </p>
          <p className="mt-5 max-w-3xl text-lg leading-relaxed text-slate-600">
            Law is dynamic, not static. Authority narrows, erodes, and shifts, often{" "}
            <Hi><span className="font-semibold text-slate-800">without a single overruling</span></Hi>. A real
            good-law check needs nuance and context, not a binary flag.
          </p>
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            {[
              ["Citators are binary", "Existing tools treat a case as one monolithic object: just “good” or “questioned.”"],
              ["So the work falls on you", "Lawyers read hundreds of citing cases by hand to learn whether their specific argument still survives."],
              ["And legal AI makes it worse", "It generates confident answers without grounding them in the current state of the law."],
            ].map(([h, b]) => (
              <div key={h} className="rounded-2xl bg-slate-50 p-5 ring-1 ring-slate-200/70">
                <p className="font-semibold text-slate-900">{h}</p>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{b}</p>
              </div>
            ))}
          </div>
          <p className="mt-8 rounded-2xl border-l-4 border-slate-900 bg-gradient-to-r from-slate-100 to-slate-50 px-5 py-4 text-lg font-medium text-slate-800">
            The nuance lives in <span className="italic">how</span> the law evolved. That is <Hi>exactly what gets lost</Hi>.
          </p>
        </Card>
      </section>

      {/* ─────────────────────────── 3 · SOLUTION ─────────────────────────── */}
      <section className="flex min-h-screen snap-start flex-col items-center justify-center px-6 py-16">
        <SlideTitle>Our Solution</SlideTitle>
        <Card>
          <Kicker>What we do</Kicker>
          <p className="mt-4 text-3xl font-bold leading-tight text-slate-900">
            We capture meaning changing <Hi>without overruling</Hi>.
          </p>
          <p className="mt-5 max-w-3xl text-lg leading-relaxed text-slate-600">
            Take the Second Amendment. From <em>Heller</em> (2008) to <em>Hemani &amp; Wolford</em> (2026),
            every case is still “good law.” But the test underneath moved:
          </p>

          <div className="mt-6 space-y-2.5">
            {cases.map((c) => (
              <div key={c.name} className="flex items-baseline gap-4 rounded-xl bg-slate-50 px-4 py-3 ring-1 ring-slate-200/70">
                <span className="w-16 shrink-0 font-mono text-sm font-semibold text-slate-400">{c.year}</span>
                <span className="w-44 shrink-0 font-semibold text-slate-900">{c.name}</span>
                <span className="text-slate-600">{c.note}</span>
              </div>
            ))}
          </div>

          <p className="mt-7 text-lg font-semibold text-slate-900">
            What makes it unique
          </p>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            {unique.map((u) => (
              <div key={u.h} className="rounded-2xl bg-slate-50 p-5 ring-1 ring-slate-200/70">
                <p className="font-semibold text-slate-900">{u.h}</p>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{u.b}</p>
              </div>
            ))}
          </div>

          <p className="mt-7 rounded-2xl border-l-4 border-slate-900 bg-gradient-to-r from-slate-100 to-slate-50 px-5 py-4 text-lg font-medium text-slate-800">
            We answer not just <span className="italic">“Is it still valid?”</span> but{" "}
            <Hi><span className="italic">“How far can you rely on it, and why?”</span></Hi>
          </p>
        </Card>
      </section>

      {/* ─────────────────────────── 4 · HOW IT WORKS (diagram) ─────────────────────────── */}
      <section className="flex min-h-screen snap-start flex-col items-center justify-center px-6 py-16">
        <SlideTitle>How It Works</SlideTitle>
        <div className="w-full rounded-[28px] bg-white p-8 shadow-2xl shadow-black/25 md:p-10">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <Kicker>From a citation to a grounded verdict</Kicker>
              <p className="mt-1 text-sm text-slate-500">Deterministic where it can be, Gemini where it has to read the opinion.</p>
            </div>
            <div className="flex items-center gap-4 text-xs text-slate-500">
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-slate-900" /> AI applied</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-slate-300" /> deterministic</span>
            </div>
          </div>

          <div className="relative mt-6 w-full aspect-[1000/440]">
            {/* edges (shared 1000x440 coordinate space with the nodes) */}
            <svg viewBox="0 0 1000 440" preserveAspectRatio="none" className="absolute inset-0 h-full w-full overflow-visible">
              <defs>
                <marker id="ah" markerWidth="7" markerHeight="7" refX="5.5" refY="3" orient="auto-start-reverse">
                  <path d="M0 0 L6 3 L0 6 Z" fill="#334155" fillOpacity="0.65" />
                </marker>
              </defs>
              {flowEdges.map((e, i) => (
                <g key={i}>
                  <path d={e.d} fill="none" stroke="#334155" strokeOpacity="0.45" strokeWidth="2" strokeDasharray={e.dashed ? "5 4" : undefined} markerEnd="url(#ah)" />
                  {e.label && <text x={e.lx} y={e.ly} textAnchor="middle" fill="#94a3b8" fontSize="6.5" fontWeight="600">{e.label}</text>}
                </g>
              ))}
            </svg>

            {/* nodes (centred on x,y of the same space) */}
            {flowNodes.map((n) => (
              <div
                key={n.id}
                style={{ left: `${n.x / 10}%`, top: `${n.y / 4.4}%` }}
                className={`absolute w-[226px] -translate-x-1/2 -translate-y-1/2 rounded-xl p-3.5 shadow-sm ring-1 ${n.intermediate ? "border border-dashed border-slate-300 bg-slate-50 ring-slate-200" : n.service ? "bg-slate-100 ring-slate-400" : "bg-white ring-slate-200"}`}
              >
                <div className="flex items-center gap-1.5">
                  <span className="text-[12px] font-bold uppercase tracking-wide text-slate-400">{n.kicker ?? "AI service"}</span>
                  {n.gemini && <span className="ml-auto whitespace-nowrap rounded bg-slate-900 px-1 py-0.5 text-[11px] font-bold uppercase tracking-wide text-white">Gemini {n.gemini}</span>}
                </div>
                <p className="mt-1 text-[16px] font-bold leading-tight text-slate-900">{n.title}</p>
                <p className="mt-1 text-[13px] leading-snug text-slate-500">{n.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─────────────────────────── 5 · IMPACT ─────────────────────────── */}
      <section className="flex min-h-screen snap-start flex-col items-center justify-center px-6 py-16">
        <SlideTitle>Impact</SlideTitle>
        <Card>
          <Kicker>Why it matters</Kicker>
          <p className="mt-4 text-3xl font-bold leading-tight text-slate-900">
            Faster than manual research, <Hi>sharper than a binary flag</Hi>, safe enough for a brief.
          </p>
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            {impact.map((i) => (
              <div key={i.big} className="rounded-2xl bg-[linear-gradient(150deg,#1e293b_0%,#0f172a_100%)] p-6 text-white shadow-lg shadow-black/20 ring-1 ring-white/10">
                <p className="text-2xl font-extrabold tracking-tight">{i.big}</p>
                <p className="mt-2.5 text-xs leading-relaxed text-white/85">{i.sub}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 grid gap-6 md:grid-cols-2">
            <div>
              <p className="font-semibold text-slate-900">Who it&apos;s for</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {["Litigators drafting briefs", "Judicial clerks", "In-house counsel", "Legal-AI guardrails"].map((w) => (
                  <span key={w} className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700 ring-1 ring-slate-200">{w}</span>
                ))}
              </div>
            </div>
            <div>
              <p className="font-semibold text-slate-900">The bigger vision</p>
              <p className="mt-3 text-sm leading-relaxed text-slate-600">
                The good-law layer every legal AI is missing: grounded authority-checking that any
                research tool or drafting assistant can call before a citation reaches a court.
              </p>
            </div>
          </div>
        </Card>
      </section>

      {/* ─────────────────────────── 6 · TEAM ─────────────────────────── */}
      <section className="flex min-h-screen snap-start flex-col items-center justify-center px-6 py-16">
        <SlideTitle>Team</SlideTitle>
        <Card>
          <div className="grid gap-5 md:grid-cols-2">
            {team.map((m) => (
              <div key={m.name} className="rounded-2xl bg-slate-50 p-6 ring-1 ring-slate-200/70">
                <p className="text-xl font-bold text-slate-900">{m.name}</p>
                <ul className="mt-3 space-y-1.5">
                  {m.bullets.map((b) => (
                    <li key={b} className="flex gap-2 text-sm leading-relaxed text-slate-600">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-900" />
                      <span>{b}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>
      </section>

      {/* ─────────────────────────── 7 · QUESTIONS ─────────────────────────── */}
      <section className="relative flex min-h-screen snap-start flex-col items-center justify-center px-6 text-center">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{ backgroundImage: "linear-gradient(white 1px,transparent 1px),linear-gradient(90deg,white 1px,transparent 1px)", backgroundSize: "54px 54px" }}
        />
        <div className="relative flex flex-col items-center">
          <Image src="/logo.png" alt="CiteMeRight" width={88} height={88} className="rounded-2xl shadow-2xl shadow-black/30 ring-1 ring-white/25" />
          <h2 className="mt-8 text-7xl font-extrabold tracking-tight text-white">Questions?</h2>
          <p className="mt-4 text-2xl font-medium text-white/80">Is it still good law?</p>
          <span className="mt-8 rounded-full border border-white/30 px-5 py-2 text-sm font-medium text-white/80">
            citemeright.com
          </span>
        </div>
      </section>

      {/* ─────────────────────────── 8 · APPENDIX (risk score) ─────────────────────────── */}
      <section className="flex min-h-screen snap-start flex-col items-center justify-center px-6 py-16">
        <SlideTitle>Appendix · Risk score</SlideTitle>
        <Card>
          <Kicker>Deterministic, not model-guessed</Kicker>
          <p className="mt-1 text-sm text-slate-500">The LLM extracts each treatment; the score is code, so every number is auditable.</p>

          {/* the formula */}
          <div className="mt-6 flex items-center justify-center gap-4 rounded-2xl bg-slate-100 py-7">
            <span className="text-2xl font-bold text-slate-900">risk</span>
            <span className="text-2xl text-slate-400">=</span>
            <div className="text-center">
              <div className="px-3 pb-1.5 font-mono text-lg text-slate-900">Σ wᵢ · sevᵢ</div>
              <div className="border-t-2 border-slate-400" />
              <div className="px-3 pt-1.5 font-mono text-lg text-slate-900">Σ wᵢ</div>
            </div>
            <span className="ml-2 text-sm text-slate-500">a court-, confidence- and<br />recency-weighted negative share</span>
          </div>

          {/* the two ingredients */}
          <div className="mt-6 grid gap-5 md:grid-cols-2">
            <div className="rounded-2xl bg-slate-50 p-5 ring-1 ring-slate-200">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Weight wᵢ (per citing case)</p>
              <div className="mt-3 flex flex-wrap items-center gap-2 font-mono text-sm text-slate-700">
                <span className="rounded bg-white px-2 py-1 ring-1 ring-slate-200">court_weight</span>
                <span className="text-slate-400">×</span>
                <span className="rounded bg-white px-2 py-1 ring-1 ring-slate-200">confidence</span>
                <span className="text-slate-400">×</span>
                <span className="rounded bg-white px-2 py-1 ring-1 ring-slate-200">recency</span>
              </div>
              <p className="mt-3 text-xs text-slate-500">Only a citer's own (self-attributed) treatment counts. Reported echoes get polarity 0.</p>
            </div>
            <div className="rounded-2xl bg-slate-50 p-5 ring-1 ring-slate-200">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Severity sevᵢ</p>
              <div className="mt-3 space-y-1.5 text-sm">
                <div className="flex justify-between"><span className="text-slate-600">strong negative (overruled, abrogated)</span><span className="font-mono font-bold text-slate-900">1.0</span></div>
                <div className="flex justify-between"><span className="text-slate-600">soft negative (limited, criticised)</span><span className="font-mono font-bold text-slate-900">0.6</span></div>
                <div className="flex justify-between"><span className="text-slate-600">neutral or positive</span><span className="font-mono font-bold text-slate-900">0.0</span></div>
              </div>
            </div>
          </div>

          {/* the bands */}
          <div className="mt-6 grid gap-3 md:grid-cols-3">
            {[
              ["#dc2626", "Red", "a binding high-court overrule (strong negative, conf ≥ floor) snaps risk to 1.0"],
              ["#d97706", "Amber", "score above the floor, or an open circuit split, or cert granted"],
              ["#16a34a", "Green", "no convergent erosion; treatment isolated or approving"],
            ].map(([c, label, desc]) => (
              <div key={label} className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: c }} />
                  <span className="text-sm font-bold text-slate-900">{label}</span>
                </div>
                <p className="mt-1.5 text-xs leading-snug text-slate-500">{desc}</p>
              </div>
            ))}
          </div>
          <p className="mt-5 text-xs text-slate-500">On conflict (binding negatives alongside binding reaffirmations) the engine abstains rather than give a confident wrong answer.</p>
        </Card>
      </section>

      {/* ─────────────────────────── 9 · APPENDIX (data) ─────────────────────────── */}
      <section className="flex min-h-screen snap-start flex-col items-center justify-center px-6 py-16">
        <SlideTitle>Appendix · Where the data comes from</SlideTitle>
        <Card>
          <Kicker>Provenance + ingestion</Kicker>
          <p className="mt-1 text-sm text-slate-500">CourtListener v4 (Free Law Project). Token-free for the graph; verbatim passages; idempotent and reproducible.</p>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {[
              ["Graph + passages", "A cited-by query returns who cites the target into citation_edges; highlighted snippets give the citing span into cl_opinions.plain_text. Verbatim, quote-verified downstream."],
              ["Full-text enrichment", "With a token, the bounded text subset is upgraded to the full opinion (rate-paced), feeding the deep full-text read."],
              ["Idempotent load", "Opinions upsert (text never overwritten with NULL); edges skip-existing. Re-running enriches, never duplicates."],
              ["Resilient fallback", "If the live source is blocked, a source='seed' set of real overrulings keeps the pipeline runnable offline / in CI."],
            ].map(([h, b]) => (
              <div key={h} className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-400">{h}</p>
                <p className="mt-1.5 text-[13px] leading-snug text-slate-600">{b}</p>
              </div>
            ))}
          </div>

          {/* schema + infra */}
          <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-slate-200 pt-4">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Schema</span>
            {["cl_opinions", "citation_edges", "treatments"].map((t) => (
              <span key={t} className="rounded-full bg-slate-100 px-3 py-1 font-mono text-xs text-slate-600 ring-1 ring-slate-200">{t}</span>
            ))}
            <span className="ml-2 text-xs text-slate-500">Cloud SQL · Postgres 16, loaded via <span className="font-mono">just load-dump</span></span>
          </div>
          <p className="mt-4 text-xs text-slate-500">Net: every verdict resolves to a real, verbatim citing passage. No synthetic data, no model-asserted authority.</p>
        </Card>
      </section>

      {/* ─────────────────────────── 10 · APPENDIX (Bruen propositions) ─────────────────────────── */}
      <section className="flex min-h-screen snap-start flex-col items-center justify-center px-6 py-16">
        <SlideTitle>Appendix · The Bruen proposition spine</SlideTitle>
        <Card>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <Kicker>One case, nine holdings, nine trajectories</Kicker>
              <p className="mt-1 text-sm text-slate-500">Why case-level is too coarse: Bruen is green on some points and eroding on others, simultaneously.</p>
            </div>
            <div className="flex items-center gap-4 text-xs text-slate-500">
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: "#16a34a" }} /> stable</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: "#d97706" }} /> contested</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: "#94a3b8" }} /> open</span>
            </div>
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-3">
            {[
              ["P1", "Public-carry right", "#16a34a", "Right to carry in public for self-defence; may-issue 'proper cause' regimes are out."],
              ["P2", "Text-history-tradition", "#16a34a", "Regulations must fit historical tradition; means-end balancing is rejected."],
              ["P2a", "Analogue, not twin", "#d97706", "Not a 'dead ringer', only relevantly similar. Loosened by Rahimi (2024)."],
              ["P3", "Sensitive places", "#d97706", "May bar carry, but the category is undefined; private-property default struck in Wolford (2026)."],
              ["P4", "Common use / AWB", "#d97706", "Arms in common use are protected; circuit split on assault weapons and magazines."],
              ["P5", "'The people' / §922(g)", "#d97706", "Who may be disarmed, the hottest split; drug-user ban narrowed in Hemani (2026)."],
              ["P6", "Era: 1791 vs 1868", "#94a3b8", "Which era fixes the tradition is reserved and open."],
              ["P7", "Shall-issue licensing", "#16a34a", "Presumptively lawful, absent exorbitant fees or abuse."],
              ["P8", "Presumptively-lawful carve-outs", "#16a34a", "Felon-in-possession, mentally ill, commercial sale survive."],
            ].map(([id, label, color, desc]) => (
              <div key={id} className="rounded-xl bg-slate-50 p-3.5 ring-1 ring-slate-200">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-white px-1.5 py-0.5 font-mono text-[11px] font-bold text-slate-900 ring-1 ring-slate-200">{id}</span>
                  <span className="text-sm font-bold text-slate-900">{label}</span>
                  <span className="ml-auto h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
                </div>
                <p className="mt-1.5 text-[11px] leading-snug text-slate-500">{desc}</p>
              </div>
            ))}
          </div>

          <p className="mt-6 rounded-2xl border-l-4 border-slate-900 bg-gradient-to-r from-slate-100 to-slate-50 px-5 py-4 text-center text-base font-medium text-slate-800">
            A binary citator flags Bruen as one thing. We track <Hi>all nine</Hi>, so the answer fits the argument you're actually making.
          </p>
        </Card>
      </section>
    </main>
  );
}
