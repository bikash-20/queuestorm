"""Application configuration loaded from environment variables.

Uses Pydantic Settings for type-safe, validated configuration.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized, environment-driven application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "queuestorm"
    app_env: Literal["development", "staging", "production"] = "production"
    log_level: str = "INFO"
    version: str = "1.0.0"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Classifier backend selection (open/closed principle - swap strategies at runtime)
    classifier_backend: Literal["rule_based", "llm"] = "rule_based"

    # Request limits
    max_message_length: int = Field(default=4000, ge=1, le=32000)

    # CORS
    allowed_origins: str = "*"

    # Safety
    enforce_safety_filter: bool = True

    # LLM (optional)
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 10

    @property
    def cors_origins(self) -> list[str]:
        if self.allowed_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (singleton)."""
    return Settings()
