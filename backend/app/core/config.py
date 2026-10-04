from functools import lru_cache

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Tripdeep API"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_backend: Literal["postgres", "mongo", "memory"] = "postgres"
    postgres_dsn: str = "host=127.0.0.1 port=5432 dbname=tripdeep user=postgres"
    mongodb_url: str = "mongodb://tripdeep:tripdeep-local@localhost:27017/?authSource=admin"
    mongodb_database: str = "tripdeep"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "tripdeep-documents"
    llm_provider: Literal["none", "ollama", "cloudflare_workers_ai"] = "none"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    ollama_timeout_seconds: float = 25.0
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    cloudflare_ai_model: str = "@cf/meta/llama-3.1-8b-instruct"
    cors_origins: list[str] = ["http://localhost:5173"]
    upload_max_bytes: int = 10 * 1024 * 1024
    upload_directory: str = "var/uploads"
    max_agent_retries: int = 2
    agent_timeout_seconds: float = 30.0
    airport_radius_km: float = 20.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def validate_production(self) -> None:
        if self.environment != "production":
            return
        missing = [
            name
            for name, value in (
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_ANON_KEY", self.supabase_anon_key),
            )
            if not value
        ]
        if self.database_backend != "postgres":
            missing.append("DATABASE_BACKEND=postgres")
        if not self.supabase_service_role_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if not any(
            mode in self.postgres_dsn.casefold()
            for mode in ("sslmode=require", "sslmode=verify-ca", "sslmode=verify-full")
        ):
            missing.append("POSTGRES_DSN with SSL enabled")
        if self.supabase_url and not self.supabase_url.startswith("https://"):
            missing.append("HTTPS SUPABASE_URL")
        if (
            not self.cors_origins
            or "*" in self.cors_origins
            or any(
                not origin.startswith("https://") or "localhost" in origin
                for origin in self.cors_origins
            )
        ):
            missing.append("CORS_ORIGINS with the deployed frontend origin")
        if self.llm_provider == "cloudflare_workers_ai" and (
            not self.cloudflare_account_id or not self.cloudflare_api_token
        ):
            missing.append("CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN")
        if missing:
            raise ValueError("Production configuration is incomplete: " + ", ".join(missing))


@lru_cache
def get_settings() -> Settings:
    return Settings()