# Handoff — Citator frontend build-out (querying the backend + expansion)

**Mode line.** Next session is **EXECUTING** a frontend expansion on top of the working citator vertical. Nothing blocks building, but **confirm one product fork first** (bold, below): the flagship is **citator-aware chat (`/ask`)** vs the **brief-checker (`/check`)`**. Recommended path: **Layer 0 (unify the query layer) → Layer 1 flagship chat**. Pair this with the classifier fixes from `citator-endpoints.md` — the chat will surface the Smith false-red / snippet noise if they aren't addressed.

## State (quantified) — what's live now
Backend (merged, CI-green; data is **local Docker DB only**, prod not deployed):
- `POST /chat` (🔒 authed, Gemini, stateful) · `POST /resolve` (🌐 public) · `GET /cases/{id}/risk` (🌐 public) · `GET /health`. (PRs #11–#13)
Frontend (merged):
- `/` — authed chat page (`components/chat` → `lib/api.ts::sendChat`). (#16 added `/citator`)
- `/citator` — public: search → `/resolve` → `/cases/{id}/risk`; signal card + CSS-bar erosion trend + treatments + 6 quick-pick chips.
- **Local auth works** (`frontend/.env.local`: real Supabase publishable key + localhost API; backend on stub verifier). Email login `demo@hacklaw.app` / `hacklaw2026`. Auth made optional so public pages don't crash (#17, #18).
Data: 6 SCOTUS cases (Roe/Plessy/Bowers/Lochner = red, Auer = green, Smith = **false-red**).

## How we query the backend today (the starting point)
- `frontend/lib/api.ts` — ONE typed fn: `sendChat(message, history)` → adds `Bearer` via `getAccessToken()`. Authed only.
- `frontend/app/citator/page.tsx` — **hand-rolls raw `fetch`** to `/resolve` (line ~110) and `/cases/{id}/risk` (line ~92), with inline types. Public (no Bearer).
- `API` base = `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080"`.
- **Gap:** no shared typed client for the citator endpoints; error/loading handling is per-call. Fix in Layer 0.

## The plan

### Layer 0 — Unify the query layer (foundation, do first; ~1 small PR)
- Extend `lib/api.ts` with typed `resolve(query): Promise<ResolveResult>` and `caseRisk(id): Promise<RiskResult>`, plus shared types (`ResolveResult`, `RiskResult`, `Treatment`, `TrendPoint`, `GroundTruth`) mirroring the backend pydantic models (`app/src/htl/models/api.py`).
- Add a tiny `request()` helper: base URL, JSON, consistent error shape, optional `auth: boolean` (adds Bearer when true). Public citator calls pass `auth:false`.
- Refactor `/citator` to import these instead of inline fetch.
- Extract a reusable **`<VerdictCard>`** component out of `citator/page.tsx` (signal badge + status/score/rationale + ground-truth + trend + treatments) so chat and citator share one renderer.
- Files: `frontend/lib/api.ts`, `frontend/app/citator/page.tsx`, new `frontend/components/verdict-card.tsx`.

### Layer 1 — Flagship: citator-aware chat (`POST /ask`)  ← recommended headline
Ask in plain English → grounded, **sourced** good-law answer (not an ungrounded LLM guess). Synthesis of chat + citator; directly showcases the *reliability* pillar.
- **Backend** new `routes/ask.py` → `POST /ask {question}` → `{answer, verdict?: RiskResult, resolved_case?}`. Logic: detect the case in the question → `resolve` → `risk` → compose a grounded NL answer citing the verdict + sources. If no case detected, fall back to plain chat.
  - **Architecture decision:** deterministic pipeline (extract→resolve→risk→summarize with Gemini) **first** — simpler, reliable, demoable — then optionally upgrade to Gemini tool-use/function-calling. Reuse `llm/vertex.py` + the risk service from `routes/risk.py`.
  - **Auth decision:** make `/ask` public (like `/citator`) for demo accessibility, or authed like `/chat`. Recommend **public** for the demo.
- **Frontend**: a chat surface (enhance `components/chat` or a new `/assistant` page) that renders the NL answer + an inline `<VerdictCard>` when a case was checked + source links. Always show signal + sources + "based on N citing cases"; never an ungrounded good-law claim.
- Files: `app/src/htl/routes/ask.py` (+ register in `main.py`), model in `models/api.py`; `frontend/lib/api.ts::ask()`, chat surface, reuse `<VerdictCard>`.

### Layer 1b — Brief checker (`POST /check`)  ← strong second / alternative
Paste a memo/brief → flag dead authorities. The concrete lawyer workflow.
- **Backend** `routes/check.py` → `POST /check {text}` → extract citations (ponytail: regex for reporter citations + case names; upgrade to `eyecite` / CL `citation-lookup` if a token lands) → `resolve`+`risk` each → `{authorities: [{citation, verdict}], summary}`.
- **Frontend** `/check` page: paste box → table of authorities with signal badges + "N of M no longer good law".

### Layer 2 — Richer citator UX (mostly reuse existing endpoints)
- Polish results: real erosion chart (ponytail: keep CSS bars / inline SVG before adding a chart dep), treatments **sortable + linked to the CourtListener source**, **confidence/uncertainty surfaced**, point-in-time "as of" date (needs a `?as_of=` param on `/risk`).
- Case-detail + **citation-graph viz** — new `GET /cases/{id}/graph` (1-hop from `citation_edges`) + a simple SVG/force viz.
- Browse/search gallery over the seeded cases + the LoC overruled set (demo entry point).

## Cross-cutting principles
- **Surface confidence + source link on every result** (reliability = the judge's emphasis; cheap to add everywhere).
- All backend calls go through `lib/api.ts` (no more inline fetch).
- Reuse `<VerdictCard>` across citator + chat + brief-checker.
- Ship every change via `.claude/skills/ship-feature/` (branch → PR → CI green → squash-merge). Frontend changes auto-deploy to Vercel on merge — but **prod backend has no citator data yet**, so keep building/testing locally and hold prod-facing merges until the backend is promoted (`just migrate` → classify against Cloud SQL → `just deploy`).

## Open questions / decisions (resolve before/early)
1. **Flagship fork — BLOCKING the Layer-1 choice:** `/ask` citator-aware chat *(recommended)* vs `/check` brief-checker first.
2. `/ask` architecture: deterministic pipeline *(recommended first)* vs Gemini tool-use.
3. `/ask` auth: public *(recommended for demo)* vs authed.
4. Chart: CSS/SVG *(ponytail, recommended)* vs add a chart lib (recharts/visx).
5. Backend quality: the Smith **false-red** + snippet noise + sparse trend (see `citator-endpoints.md`) will show up in chat answers — schedule the expert-tuned classifier pass alongside Layer 1, or the flagship demo inherits the bug.

## First moves
1. Skim `STATE.md`, this brief, and `.claude/handoffs/citator-endpoints.md` (the backend/classifier state + the #1 false-red fix). The 3 expert questions (in chat) tune the risk logic the chat will surface.
2. Confirm decision #1 (flagship fork) and #2/#3.
3. **Layer 0** — unify `lib/api.ts` (typed `resolve`/`caseRisk` + `request()` helper), refactor `/citator`, extract `<VerdictCard>`. One PR.
4. Build the flagship: `/ask` backend (deterministic pipeline) → chat surface rendering `<VerdictCard>` + sources. Ship-feature.
5. Layer 2 polish as time allows.

## Teardown note
Delete this handoff (move to `.claude/handoffs/archive/`) when the Layer-0/Layer-1 build is underway and this plan is superseded by real PRs.
