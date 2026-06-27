from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App config. Reads .env.local for local dev; Cloud Run injects env vars at deploy."""

    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    gcp_project: str = "llm-law-cambridge26cbx-522"  # overridden by GCP_PROJECT on Cloud Run
    vertex_location: str = "global"  # Gemini lives here
    gemini_model: str = "gemini-2.5-flash"  # default for any unmapped task

    # --- Task → model routing (see llm/router.py) ---------------------------
    # No model id is hardcoded in feature code — call sites ask the router for
    # "the model for task T". Account-portable + env-overridable, like the infra
    # rule for GCP values: override the whole table with MODEL_ROUTES='{...}' (JSON)
    # or one task with HTL_MODEL_<TASK> (e.g. HTL_MODEL_ANALYZE=claude-opus-4-8).
    # Defaults use only Gemini models callable on Vertex with zero enablement, so CI
    # and the live default path need no Claude/MaaS setup. claude_location/maas_location
    # are where the router *would* dispatch those providers (us-central1, not global).
    model_routes: dict[str, str] = {
        "classify": "gemini-2.5-flash",  # F2 snippet treatment labels (cheap, high volume)
        "analyze": "gemini-3.1-pro-preview",  # F3 deep full-opinion read — the one Pro task
        "narrative": "gemini-3.5-flash",  # F4 "what changed" prose
        "usemap": "gemini-3.5-flash",  # F5 use → proposition mapping
        "ask": "gemini-2.5-pro",  # the flagship agentic /ask loop
    }
    # On a model error (404 / quota / not-enabled) the router hops to the next model.
    # Preview models have tighter quotas → the GA fallback is not optional. The claude
    # entry documents the degrade-to-Gemini path while Claude stays behind enablement.
    model_fallbacks: dict[str, str] = {
        "gemini-3.1-pro-preview": "gemini-2.5-pro",
        "claude-opus-4-8": "gemini-3.1-pro-preview",
    }
    claude_location: str = "us-central1"  # Anthropic partner models are region-pinned
    maas_location: str = "us-central1"  # open MaaS (deepseek/gpt-oss) endpoint region

    # --- Database -----------------------------------------------------------
    # Cloud SQL via the connector when instance_connection_name is set (prod +
    # local-against-cloud). database_url is a plain-Postgres fallback for a local
    # container. Both empty → the app boots but DB-backed routes error on first
    # use (and tests override the session dependency, so they never connect).
    instance_connection_name: str = ""
    db_user: str = "htl_app"
    db_password: str = ""
    db_name: str = "htl"
    database_url: str = ""

    # --- Supabase auth (verify-only; JWKS is public-key material) -----------
    # Both JWKS url + issuer present → the real verifier gates requests; absent →
    # the dev/CI stub. supabase_audience is the standard Supabase access-token aud.
    supabase_jwks_url: str = ""
    supabase_issuer: str = ""
    supabase_audience: str = "authenticated"

    log_level: str = "INFO"

    # Comma-separated; "*" allows any origin (fine for a hackathon).
    # ponytail: comma-split instead of a JSON-list env to dodge pydantic env-parsing.
    cors_origins: str = "*"

    system_prompt: str = (
        "You are a helpful legal assistant for the Hack the Law Cambridge 2026 project. "
        "Answer clearly and reference general legal principles where relevant. "
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
