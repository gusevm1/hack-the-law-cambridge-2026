# Feature 4 (B) — Proposition evolution + risk + trajectory

You're building the **aggregation** stage: turn per-case findings into a per-
proposition verdict — how each proposition evolved, its quantified risk, and the
trajectory signals (circuit split · cert pending · close-to-overruled). Fresh
session — read before coding.

## Read first (in order)
1. `.claude/CLAUDE.md` + `STATE.md`.
2. `.claude/handoffs/citator-pipeline-scope.md` — §4 spine, §5 golden example, §9
   (the parked AWB/LCM cert cluster — your cert-watch seed; **re-verify dates**).
3. `.claude/handoffs/citator-pipeline-contracts.md` — **Contract A is your input,
   Contract B is your output.**
4. Invoke `ship-feature` BEFORE coding. ponytail. Branch: `feat/citator-proposition-evolution`.

## What you're building
Backend `GET /cases/{id}/propositions → PropositionsResponse` (Contract B) + the
stepper's **Relation** step. Bucket the analyzed findings (Contract A, **mock to
contract** — Feature 3 builds it in parallel) by proposition, then per proposition:

- **timeline** — chronological treatments (court-weighted), polarity per point.
- **risk_score + signal** — reuse `risk.py` helpers (`court_weight`, `_recency_factor`,
  the dispositive-strong-negative rule). This is **code, not the model.**
- **what_changed** — a grounded narrative of the evolution (LLM may draft, but every
  claim ties to a finding's quote; verbatim-verify).
- **circuit_split** — DERIVED, deterministic: group findings by `(proposition ×
  circuit × polarity)`; divergence among federal circuits ⇒ `present=true`, list
  `follows`/`limits`. Live example in the data: **P5/§922(g)** — Jackson (CA8,
  upholds) vs Range (CA3, strikes as-applied).
- **cert** — from a **cert-watch table you own** (curated dict, dated, keyed by
  proposition/case — same discipline as `GROUND_TRUTH` in `risk.py`). **Code-grounded
  only; never let the LLM assert a cert grant.** Sources: supremecourt.gov order
  lists, SCOTUSblog, CL dockets. Note: Wolford v. Lopez shows a `scotus/2026` docket
  entry — a real cert signal to chase.
- **close_to_overruled** — trajectory synthesis: accelerating high-court negatives +
  split width + cert pending. **Abstain ("needs review") when signals conflict.**
- **operative_rule** — compose "Bruen, good law as modified by Rahimi (2024)."

## Build
- Keep the aggregation a **pure function** (mirror `risk.py::aggregate_risk`):
  `aggregate_propositions(findings, …) -> PropositionsResponse`, unit-testable with
  synthetic findings. The LLM (narrative only) and cert-table are injected/separate.
- New module `citator/evolution.py` (pure) + `citator/certwatch.py` (the table) +
  route `routes/propositions.py`. Models per Contract B in `api.py`. Register in `main.py`.
- Frontend: own step file `app/citator/analyze/steps/relation.tsx`; per-proposition
  cards with the signal, what_changed, a CSS timeline (reuse the erosion-bar idiom in
  `components/verdict-card.tsx`), and split/cert/close-to-overruled badges.

## Acceptance
- `just lint && just test` green; pure-function unit test: a P5 split (CA8 follows /
  CA3 limits) → `circuit_split.present`; a dispositive high-court negative → red; a
  cert-flagged proposition surfaces `cert.granted`; conflicting signals →
  `close_to_overruled` abstains. Counts/propositions stable.
- `pnpm build` clean; Relation step renders Bruen (P1 green, P2a amber, P5 split).
- PR vs main, CI green, preview checked. Deploy with `PROJECT_ID=…`.

## Boundaries
- You consume per-edge findings and emit **per-proposition** verdicts. **No
  use-matching** (that's C). No deep reading of opinions (that's A).
- cert + close-to-overruled are **code/curated-grounded**, dated, abstaining — the
  malpractice boundary.
- Contract-first: FE mirrors `PropositionsResponse` exactly.
