from pydantic_settings import BaseSettings
from typing import List, Literal, Optional
import sys


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "research_dataset_builder"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    duckdb_path: str = "./data/warehouse.duckdb"

    # Authentication
    jwt_secret_key: str = "demo-secret-key-change-in-production-please-use-setup-sh"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # CORS — comma-separated list of allowed origins
    cors_origins: str = "*"

    # LLM
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    llm_provider: Literal["openai", "anthropic"] = "openai"

    # FHIR
    fhir_base_url: Optional[str] = None
    fhir_auth_token: Optional[str] = None

    # Application
    app_env: str = "development"
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> List[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def postgres_url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

# Warn loudly if the default dev secret is used outside development
_DEFAULT_SECRET = "dev-secret-key-change-in-production-12345678901234567890"
if settings.jwt_secret_key == _DEFAULT_SECRET and settings.app_env != "development":
    print(
        "CRITICAL: JWT_SECRET_KEY is still set to the default development value. "
        "Set a strong random key before deploying.",
        file=sys.stderr,
    )
