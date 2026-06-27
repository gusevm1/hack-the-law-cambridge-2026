from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App config. Reads .env.local for local dev; Cloud Run injects env vars at deploy."""

    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    gcp_project: str = "llm-law-cambridge26cbx-522"  # overridden by GCP_PROJECT on Cloud Run
    vertex_location: str = "global"
    gemini_model: str = "gemini-2.5-flash"
    ask_model: str = "gemini-2.5-pro"  # the flagship agentic /ask uses the max model

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
