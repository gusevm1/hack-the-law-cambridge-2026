from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App config. Reads .env.local for local dev; Cloud Run injects env vars at deploy."""

    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    gcp_project: str = "hack-the-law-cambridge-2026"
    vertex_location: str = "global"
    gemini_model: str = "gemini-2.5-flash"

    # Comma-separated; "*" allows any origin (fine for a hackathon).
    # ponytail: comma-split instead of a JSON-list env to dodge pydantic env-parsing.
    cors_origins: str = "*"

    system_prompt: str = (
        "You are a helpful legal assistant for the Hack the Law Cambridge 2026 project. "
        "Answer clearly and reference general legal principles where relevant. "
        "Always remind the user that this is general information, not legal advice."
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
