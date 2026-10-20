from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
# Explicit paths avoid find_dotenv stopping at backend/.env and hiding root credentials.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "backend" / ".env")


class Settings:
    DEBUG: bool = os.getenv("DEBUG", "0") == "1"

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:docuchat123@localhost:5436/docuchat",
    )

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gpt-6-luna")
    CHAT_MODELS: list[str] = list(dict.fromkeys([DEFAULT_MODEL] + [
        m.strip() for m in os.getenv("CHAT_MODELS", "").split(",") if m.strip()
    ]))
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "backend/uploads")
    INDEX_DIR: str = os.getenv("INDEX_DIR", "backend/faiss_indexes")

    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))

    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    ALLOWED_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if o.strip()
    ]


settings = Settings()
