from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _get(key: str, default: str | None = None) -> str | None:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return val


class Config:
    PROJECT_ROOT: Path = PROJECT_ROOT
    DB_PATH: Path = PROJECT_ROOT / (_get("DB_PATH", "data/suge_tutor.db") or "data/suge_tutor.db")
    QUESTIONS_JSON: Path = PROJECT_ROOT / "data" / "questions.json"

    LLM_PROVIDER: str = _get("LLM_PROVIDER", "moonshot") or "moonshot"
    LLM_BASE_URL: str = _get("LLM_BASE_URL", "https://api.moonshot.ai/v1") or "https://api.moonshot.ai/v1"
    LLM_API_KEY: str = _get("LLM_API_KEY", "") or ""
    LLM_MODEL: str = _get("LLM_MODEL", "kimi-k2-0905-preview") or "kimi-k2-0905-preview"
    LLM_TEMPERATURE: float = float(_get("LLM_TEMPERATURE", "0.2") or "0.2")
    LLM_MAX_TOKENS: int = int(_get("LLM_MAX_TOKENS", "2000") or "2000")
    LLM_TIMEOUT_SECONDS: float = float(_get("LLM_TIMEOUT_SECONDS", "60") or "60")
    LLM_CONCURRENCY: int = int(_get("LLM_CONCURRENCY", "4") or "4")


config = Config()
