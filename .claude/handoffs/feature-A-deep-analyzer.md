# Feature 3 (A) — Deep per-case analyzer

You're building the **deep analysis** stage of the proposition-level citator. Fresh
session — read before coding. Heavy parallel GCP compute is sanctioned; spend it.

## Read first (in order)
1. `.claude/CLAUDE.md` + `STATE.md` (where we are).
2. `.claude/handoffs/citator-pipeline-scope.md` — §3 retrieval, §4 proposition spine,
   §5 Bruen golden example.
3. `.claude/handoffs/citator-pipeline-contracts.md` — **Contract A is your output.**
4. `.claude/handoffs/retrieval-ingestion-contract.md` — the full-text source rule.
5. Invoke `ship-feature` BEFORE coding. ponytail applies. Branch: `feat/citator-deep-analyzer`.

## What you're building
Backend `GET /cases/{id}/analyze → AnalyzeResponse` (Contract A) + upgrade the
stepper's **Treatment** step to render deep findings. This **supersedes the depth of
Feature 2's `/classify`** (snippet-only) — reuse `classify_edge` as the snippet path.

The job: for each **deep+shallow** edge (mentions skip), read the citing opinion and
emit **per-proposition findings** — one case can touch several propositions
(treatment · what_changed · holding/dicta · attribution · verbatim quote · conf) +
a one-line `case_summary`. Fan out across edges in parallel (`asyncio.gather`).

## Graceful degradation (the core design)
Full text is only sometimes available (CL has Rahimi's 222K-char opinion but returns
**empty** for recent F.4th cases — verified). So:
- **full-text mode:** when the opinion text is present, multi-pass deep read —
  *locate* every passage discussing the target (handles cited-by-name, multi-para),
  then classify each per-proposition, then compile. Set `analysis_depth="full-text"`.
- **snippet mode:** when only the `passage` snippet exists, fall back to the
  Feature-2 `classify_edge` path, wrap as a single finding, **lower confidence**,
  `analysis_depth="snippet"`. Never pretend to depth you didn't have.

**Full-text source (wishful, per locked decision #2):** assume retrieval persists the
full opinion in `cl_opinions.plain_text` keyed by the citing opinion id, and the
edge carries that id. The retrieval engineer is solving sourcing — **do not fetch CL
yourself.** Until the real data lands, mock it: extend the Bruen stub
(`citator/golden.py`) so a couple of edges carry real/representative full text (e.g.
Rahimi) and the rest carry only snippets — exercising both modes.

## Build
- Pure-ish where possible; the LLM read is the one impure part. Mirror `llm/classify.py`
  (Vertex client, `temperature=0`, schema-constrained, **verbatim-quote verified**,
  keyword fallback). New module e.g. `llm/analyze.py`; route `routes/analyze.py`.
- Multi-pass full-text read may itself fan out (locate → per-passage classify →
  compile, optional self-consistency verify on a "red"). Parallel is fine.
- Models in `models/api.py` per Contract A. Register in `main.py`.
- Frontend: own step file `app/citator/analyze/steps/treatment.tsx`; point the
  Treatment step at `/analyze`; group findings by proposition; show `analysis_depth`
  + model as provenance; highlight the verbatim quote in the passage.

## Acceptance
- `just lint && just test` green; add a pure/mocked unit test (LLM stubbed):
  full-text edge → multiple findings + `analysis_depth="full-text"`; snippet edge →
  one finding + `"snippet"`; mention → not analyzed; `analyzed == deep+shallow`.
- `pnpm build` clean. Treatment step renders Bruen end-to-end, grouped by proposition.
- PR vs main, CI green, Vercel preview checked. Deploy: `PROJECT_ID=llm-law-cambridge26cbx-522 just deploy`.

## Boundaries
- You produce per-edge per-proposition findings. **You do NOT aggregate across edges**
  into proposition verdicts (that's Feature 4/B) and do NOT do use-matching (C).
- No real retrieval / no CL fetching — consume persisted full text by id (mock it).
- Contract-first: FE types mirror `AnalyzeResponse` exactly.
