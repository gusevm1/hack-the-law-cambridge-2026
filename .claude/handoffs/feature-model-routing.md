# Feature — Model routing layer

Build a thin **model-routing layer** so any pipeline call site asks for "the model for
task T" and gets a configured client — letting us route cheap tasks through Flash and
expensive reasoning (deep analysis, verdicts) through frontier/premium models
(`gemini-3.1-pro-preview`, and Claude Opus once enabled), with graceful fallback.

## Read first (in order)
1. `.claude/CLAUDE.md` + `STATE.md` (where we are; account-portable infra rule).
2. `.claude/handoffs/vertex-models.md` — **the verified model catalog + per-provider call
   specifics.** Your source of truth for what's callable and how.
3. The existing LLM pattern: `app/src/htl/llm/vertex.py` (ADC client, location `global`),
   `app/src/htl/llm/classify.py` (Vertex + `temperature=0` + schema + verbatim-quote check +
   keyword fallback), `app/src/htl/settings.py` (`gemini_model`, `ask_model`).
4. Invoke `ship-feature` BEFORE coding. **Work in your OWN git worktree** — other sessions
   are concurrently editing this repo (the citator features); never share a working tree.
   Branch `feat/model-routing` off `origin/main`.

## The job
One place that maps **logical task → model**, infers the **provider** from the model id,
dispatches the call, and **falls back** when the preferred model is unavailable. Existing
call sites stop hardcoding a model and route through it.

### 1. Routing table in settings (account-portable, env-overridable)
No model id hardcoded in feature code — all flow through `settings`, like the infra rule
for GCP values. Add a task→model map + a fallback, env-overridable:

```python
# settings.py  (illustrative — keep it ponytail)
model_routes: dict[str, str] = {
    "classify":  "gemini-2.5-flash",        # F2 snippet labels (bump to 3.5-flash if desired)
    "analyze":   "gemini-3.1-pro-preview",  # F3 deep read — the one task that needs Pro
    "narrative": "gemini-3.5-flash",        # F4 "what changed" prose
    "usemap":    "gemini-3.5-flash",        # F5 use→proposition mapping
    "ask":       "gemini-2.5-pro",          # agentic /ask
}
model_fallbacks: dict[str, str] = {        # used on 404 / quota / not-enabled
    "gemini-3.1-pro-preview": "gemini-2.5-pro",
    "claude-opus-4-8":        "gemini-3.1-pro-preview",
}
```
Allow per-task override via env (e.g. `HTL_MODEL_ANALYZE=claude-opus-4-8`). A "cheap
profile" env that forces everything to flash for local/CI is a nice-to-have.

### 2. `llm/router.py` — provider-agnostic dispatch
- `model_for(task) -> str` — the configured id (env override > table).
- `provider_of(model) -> "gemini" | "claude" | "maas"` — inferred by prefix
  (`gemini-*` → gemini/global · `claude-*` → claude/us-central1 · `deepseek-*`/`gpt-oss-*`
  → maas/us-central1).
- `async def complete(task, *, system, prompt, schema=None, temperature=0.0) -> str | dict`
  — dispatch to the right provider, return text or schema-validated JSON, **preserving the
  verbatim-quote discipline** the callers rely on. On a provider error that means
  "unavailable" (404 / permission / quota), retry once with the fallback model, then the
  keyword fallback where the caller has one. Reuse `vertex._get_client()` for gemini.

### 3. Provider clients (only build what a configured model needs)
- **Gemini** (default, today): existing `google-genai`, location `global`, `response_schema`.
- **Claude on Vertex** (behind config; needs the console Enable first): add `anthropic[vertex]`
  dep, `AsyncAnthropicVertex(project=…, region="us-central1")`, JSON via tool-use. Keep it
  inert unless a `claude-*` model is actually routed — so CI/tests pass without it enabled.
- **Open MaaS** (DeepSeek/gpt-oss): raw `httpx` POST to the OpenAI-compatible
  `…/locations/us-central1/endpoints/openapi/chat/completions` with an ADC bearer token.

### 4. Migrate the committed call sites
Point `classify.py` (`classify_treatment`, `classify_edge`) and `ask.py` at the router (task
names `classify`, `ask`). No behavior change on the default routes. **Do NOT rewrite the
in-flight feature modules** (`analyze.py`/`evolution.py`/`verdict.py` — built by other
sessions). Instead, document the contract: those features call `router.complete("analyze"|
"narrative"|"usemap", …)`. They adopt it on integration (or a tiny follow-up migrates them).

## Cost & safety (do not skip)
- Premium routing has real cost. The **deep analyzer fans out** (edges × full opinions) — that
  multiplies `analyze`'s model cost. Keep the fan-out on the routed `analyze` model and the
  cheap stages on flash. Per `.claude/CLAUDE.md`: before batch/parallel LLM ops, sanity-check
  worst-case cost.
- Preview models (`gemini-3.1-pro-preview`) have tighter quotas → the fallback path is not
  optional; make it real and tested.

## Acceptance
- `just lint && just test` green; unit tests (no live LLM): `model_for` resolves table + env
  override; `provider_of` prefix inference; fallback fires on a simulated 404; `classify`/`ask`
  still work through the router (mocked).
- `pnpm build` clean if any FE touched (likely none).
- Default config uses only callable Gemini models, so CI needs no Claude/MaaS enablement.
- PR vs main, CI green. Deploy is backend: `PROJECT_ID=llm-law-cambridge26cbx-522 just deploy`.

## Boundaries
- ponytail: a settings dict + a dispatch function + fallback. **No** provider-plugin framework,
  no per-model class hierarchy. Build the Claude/MaaS paths thin and only-if-configured.
- Account-portable: no hardcoded model ids in feature code; everything via `settings`.
- Claude path stays behind config + the (separate, console) enablement — don't make tests or
  the default path depend on it.
