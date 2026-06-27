# Vertex AI — available models (verified)

Verified live against project `llm-law-cambridge26cbx-522` on 2026-06-27 (read-only,
real minimal API calls as our ADC identity). The factual base for model routing.

## Callable today (zero setup)

| Model | Tier | Region | GA/preview |
|---|---|---|---|
| `gemini-3.1-pro-preview` | Pro (frontier reasoning) | global, us-central1 | preview |
| `gemini-3.5-flash` | Flash | global | GA |
| `gemini-2.5-pro` | Pro | global, us-central1, us-east5, europe-west1 | GA |
| `gemini-2.5-flash` | Flash | global (+regions) | GA — **current repo default** |
| `gemini-3-flash-preview`, `gemini-3.1-flash-lite`, image/tts variants, `gemini-embedding-2` | — | global | mixed |
| `deepseek-r1-0528-maas` | open reasoning | us-central1 | GA |
| `gpt-oss-120b-maas` | open (OpenAI) | us-central1 | GA |

**Most powerful callable today: `gemini-3.1-pro-preview`.** (Preview ⇒ tighter quotas,
behavior can change, may be deprecated — pair with a GA fallback like `gemini-2.5-pro`.)

## In catalog but BLOCKED (404 until enabled)

`anthropic/claude-opus-4-8` (+ `-4-7`/`-4-6`/`-4-5`, `sonnet-4-6`/`-4-5`, `haiku-4-5`,
`fable-5`), `meta/llama-3.3-70b`, `meta/llama-4-maverick`, Mistral MaaS.

- Enablement is a **Cloud Marketplace ToS order — console-only** (no gcloud/REST verb).
  Model Garden → model → **Enable** → accept terms. Project-level (the Cloud Run SA is
  also 404 until then). May be blocked on this managed sandbox (order perm is
  billing-account-scoped). Re-test: `…/publishers/anthropic/models/claude-opus-4-8:rawPredict`
  returns 200 instead of 404.

## Self-host (Model Garden deployable)

Hundreds of open models deployable to a Vertex endpoint (Llama, Gemma, Mixtral, Qwen,
DeepSeek-R1 incl 70B, gpt-oss) — but **GPU quota is 0** (A100/L4) on this project, so
**not feasible here** without a quota bump a managed sandbox won't grant.

## How each provider is called

- **Gemini** — `google-genai` SDK, location **`global`**, `generateContent`, JSON via
  `response_schema`. (What the repo uses: `htl/llm/vertex.py` + `classify.py`.)
- **Claude on Vertex** — different SDK (`anthropic[vertex]` → `AnthropicVertex`), region
  **`us-central1`** (NOT `global`), `rawPredict`, body
  `{"anthropic_version":"vertex-2023-10-16","messages":[…],"max_tokens":N}`. JSON via tool-use.
- **Open MaaS (DeepSeek/gpt-oss)** — OpenAI-compatible:
  `POST https://us-central1-aiplatform.googleapis.com/v1/projects/<P>/locations/us-central1/endpoints/openapi/chat/completions`,
  body `{"model":"deepseek-ai/deepseek-r1-0528-maas","messages":[…]}`, ADC bearer token.

## Gotchas
- ADC needs a quota project: `--billing-project=<P>` (gcloud) / `x-goog-user-project: <P>` (curl).
- Claude is region-pinned (us-central1 full lineup; us-east5/eu-west1 limited) — not on `global`.
- The `boss::NOT_AUTHORIZED` user-vs-SA quirk is a *predict 403* (not reproduced for Gemini); the
  Claude/Llama block is a *different* thing (project-level 404, enablement-gated).
