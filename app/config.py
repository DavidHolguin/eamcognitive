"""
Configuration Management - Pydantic Settings
Uses Vercel AI Gateway as unified LLM endpoint
"""

from functools import lru_cache
from typing import Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Vercel AI Gateway provides OpenAI-compatible endpoint for all LLM providers.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Vercel AI Gateway (OpenAI-compatible)
    # ─────────────────────────────────────────────────────────────────────────
    vercel_ai_gateway_url: str = Field(
        default="https://ai-gateway.vercel.sh/v1",
        description="Vercel AI Gateway base URL (OpenAI-compatible)"
    )
    vercel_ai_gateway_token: SecretStr = Field(
        ...,
        description="Vercel AI Gateway API token"
    )
    
    # Default model for agents (can be overridden per-agent in DB)
    default_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Default LLM model ID"
    )
    default_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0
    )
    
    # Embedding model
    embedding_model: str = Field(
        default="openai/text-embedding-3-small",
        description="Model for vector embeddings"
    )
    embedding_dimensions: int = Field(
        default=1536,
        description="Embedding vector dimensions"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Supabase Configuration
    # ─────────────────────────────────────────────────────────────────────────
    supabase_url: str = Field(
        ...,
        description="Supabase project URL"
    )
    supabase_anon_key: SecretStr = Field(
        ...,
        description="Supabase anonymous/public key"
    )
    supabase_service_role_key: SecretStr = Field(
        ...,
        description="Supabase service role key (for admin operations)"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Application Settings
    # ─────────────────────────────────────────────────────────────────────────
    app_name: str = Field(
        default="EAM Cognitive OS",
        description="Application display name"
    )
    app_version: str = Field(
        default="2.0.1"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    # CORS origins for frontend
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Security Settings
    # ─────────────────────────────────────────────────────────────────────────
    hitl_timeout_hours: int = Field(
        default=24,
        description="Hours before HITL request expires"
    )
    max_agent_iterations: int = Field(
        default=10,
        description="Maximum iterations per agent execution"
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Institutional Context (Single-Tenant)
    # ─────────────────────────────────────────────────────────────────────────
    institution_name: str = Field(
        default="Institución Universitaria EAM"
    )
    institution_location: str = Field(
        default="Armenia, Quindío, Colombia"
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
