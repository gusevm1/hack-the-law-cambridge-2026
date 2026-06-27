# Handoff — Open Citator endpoints (resolve + risk)

**Mode line.** Next session is **EXECUTING**: extend a working vertical slice. Nothing blocks building. Do the **expert meeting early** (3 questions, in chat history) — it tunes the risk formula and yields the demo gold-case set.

## State (quantified)
Working, VERIFIED live, merged to `main` (all CI green). Data lives in the **local Docker Postgres only** — prod Cloud SQL is NOT migrated/deployed.
- **PR #11** — data foundation: tables `cl_opinions` / `citation_edges` / `treatments` (Alembic `0002`), ingestion `app/scripts/ingest_citator.py`. 150 opinions, 157 edges, 4 SCOTUS cases.
- **PR #12** — `POST /resolve` (public): citation/name → CL cluster id; `found:false` is the anti-hallucination gate.
- **PR #13** — treatment classifier (`app/src/htl/llm/classify.py`, Gemini-on-Vertex, keyword fallback) + `GET /cases/{id}/risk` (public): `signal / status / risk_score / trend / negative_treatments / ground_truth`. 157 passages classified (Vertex, no fallback needed); all 4 cases red/overruled with correct ground-truth attribution.
- Orchestrator smoke test on fresh server / current main: both endpoints green.

## Carry-over notes (decisions + gotchas)
- **Product locked: US / CourtListener, depth-first.** Question "is it still good law?" answered as a forward-looking **erosion/risk score** — source-grounded, ensemble-confidence (judge feedback). 3 pillars: Risk (differentiator) · Reliability (trust) · Status (floor, vs LoC overruled list).
- **No CL token.** Data comes from the unauth CL **search** endpoint (`q=cites:(<id>) "<cite>"&highlight=on` → inbound graph + citing snippet). `opinions`/`opinions-cited` are **401** without a token; a token only upgrades snippets → full opinion text.
- **Local dev DB:** Docker `htl-citator-pg` on **:5433**; `app/.env.local` (gitignored) sets `DATABASE_URL`. Run `cd app && uv run alembic upgrade head`, then `just dev-api`.
- **id space:** `/resolve` `case_id` == `cl_opinions.id` == `citation_edges.cited_id` == CL cluster id. Targets: **Roe 108713, Plessy 94508, Bowers 111738, Lochner 96276.**
- **Gotchas:** verify live via `just dev-api` (uvicorn, one loop) — a multi-request FastAPI TestClient crashes ("attached to a different loop"). curl **`127.0.0.1:8080`**, not `localhost` (`::1:8080` is squatted).
- **Risk formula = ponytail v1** (court+recency-weighted negative share; any high-court overruled@conf≥0.6 → dispositive red). Thresholds documented, **expert-tunable**.
- **Data-quality caveat:** passages are search-snippet-sized → a few over-labels (e.g. a Citizens United snippet containing "overruled" mis-tagged under Plessy). Demo verdicts are still correct because the dispositive path + 4-case ground-truth map anchor them. Confidence is single-model.

## Open questions / operator decisions (none block building)
- **Ensemble upgrade** (approved D2: Gemini + Claude both on Vertex) — not yet built; single-model now. `classify.py` is the seam. This is the reliability story.
- **Add a not-yet-overruled "amber" case** — all 4 current cases are red/overruled (they show the historical erosion arc, not a live amber warning). Need ≥1 contested-but-standing case to demo the erosion feature itself.
- **Deploy to prod?** Local-only now. To ship: `just migrate` (apply `0002` to Cloud SQL) → run classifier against prod DB → `just deploy`.

## First moves
1. Skim `STATE.md` + this brief. Endpoints are live: `just dev-api`, then `curl 127.0.0.1:8080/cases/108713/risk`.
2. Expert meeting (3 questions in chat) → lock risk-formula weights + get gold cases (esp. an "eroded-then-fell" and an "eroded-but-survived").
3. Build the ensemble classifier (Gemini + Claude on Vertex) at `app/src/htl/llm/classify.py`.
4. Ingest + classify 1–2 not-yet-overruled cases to demo amber/erosion; expand ground-truth beyond the 4-case stub.

## Teardown note
Delete this handoff (move to `.claude/handoffs/archive/`) when consumed.
