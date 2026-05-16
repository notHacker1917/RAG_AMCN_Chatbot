"""
Centralised configuration using `pydantic-settings`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration container."""

    # Flask
    flask_env: Literal["development", "production", "testing"] = "development"
    flask_debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 5000
    api_secret_key: str = "change-me"

    # Streamlit
    streamlit_port: int = 8501
    api_base_url: str = "http://localhost:5000"

    # Database
    database_url: str = "sqlite:///:memory:"
    db_echo: bool = False

    # Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 1024
    claude_temperature: float = 0.2

    # Embeddings / RAG
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dim: int = 1024
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 5
    faiss_index_path: str = "./storage/faiss_index/notes.index"
    faiss_meta_path: str = "./storage/faiss_index/notes_meta.pkl"

    # Storage
    raw_files_dir: str = "./storage/raw_files"
    processed_dir: str = "./storage/processed"
    max_upload_mb: int = 50

    # Logging
    log_level: str = "INFO"
    log_dir: str = "./logs"

    # MPC
    mpc_num_parties: int = 3
    mpc_prime: int = 2_147_483_647

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def project_root(self) -> Path:
        """Project root (parent of `config/`)."""
        return Path(__file__).resolve().parent.parent

    def resolve(self, p: str) -> Path:
        """Resolve a possibly-relative path against the project root."""
        path = Path(p)
        return path if path.is_absolute() else (self.project_root / path).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()


settings = get_settings()
