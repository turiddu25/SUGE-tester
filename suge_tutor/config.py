from __future__ import annotations

import os
import tempfile
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent.parent
def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for key, value in dotenv_values(path).items():
        if value:
            os.environ[key] = value


if not os.getenv("VERCEL"):
    _load_env_file(PROJECT_ROOT / ".env")
    _load_env_file(PROJECT_ROOT / ".env.local")
    _load_env_file(PROJECT_ROOT / ".env.development.local")


def _get(key: str, default: str | None = None) -> str | None:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return val


def _path_from_env(key: str, default: Path) -> Path:
    raw = _get(key)
    if not raw:
        return default
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _default_db_path() -> Path:
    if os.getenv("VERCEL"):
        return Path(tempfile.gettempdir()) / "suge_tutor.db"
    return PROJECT_ROOT / "data" / "suge_tutor.db"


class Config:
    PROJECT_ROOT: Path = PROJECT_ROOT
    DB_PATH: Path = _path_from_env("DB_PATH", _default_db_path())
    DATABASE_URL: str = (
        _get("DATABASE_URL")
        or _get("POSTGRES_URL")
        or _get("POSTGRES_PRISMA_URL")
        or _get("POSTGRES_URL_NON_POOLING")
        or _get("NEON_DATABASE_URL")
        or ""
    )
    DB_BACKEND: str = "postgres" if DATABASE_URL else "sqlite"
    QUESTIONS_JSON: Path = PROJECT_ROOT / "data" / "questions.json"

    LLM_PROVIDER: str = _get("LLM_PROVIDER", "moonshot") or "moonshot"
    LLM_BASE_URL: str = _get("LLM_BASE_URL", "https://api.moonshot.ai/v1") or "https://api.moonshot.ai/v1"
    LLM_API_KEY: str = _get("LLM_API_KEY", "") or ""
    LLM_MODEL: str = _get("LLM_MODEL", "kimi-k2-0905-preview") or "kimi-k2-0905-preview"
    LLM_TEMPERATURE: float = float(_get("LLM_TEMPERATURE", "0.2") or "0.2")
    LLM_MAX_TOKENS: int = int(_get("LLM_MAX_TOKENS", "2000") or "2000")
    LLM_TIMEOUT_SECONDS: float = float(_get("LLM_TIMEOUT_SECONDS", "60") or "60")
    LLM_CONCURRENCY: int = int(_get("LLM_CONCURRENCY", "4") or "4")
    APP_SECRET_KEY: str = _get("APP_SECRET_KEY", "dev-secret-change-me") or "dev-secret-change-me"
    APP_KEY_FREE_CALL_LIMIT: int = int(_get("APP_KEY_FREE_CALL_LIMIT", "20") or "20")
    ADMIN_EMAIL: str = _get("ADMIN_EMAIL", "calling.nardo@gmail.com") or "calling.nardo@gmail.com"
    ALLOW_LOCAL_USER_PICKER: bool = (_get("ALLOW_LOCAL_USER_PICKER", "0" if os.getenv("VERCEL") else "1") or "0").lower() in {"1", "true", "yes"}

    # Exam date — drives the spaced-repetition scheduler so intervals compress
    # as the exam approaches and never push a question past it.
    EXAM_DATE: str = _get("EXAM_DATE", "2026-05-15") or "2026-05-15"

    # Per-million-token prices in USD for Kimi K2.6 cost tracking. Verified May
    # 2026 against the official platform.kimi.ai pricing page. Cache-hit input
    # tokens are billed at a 6x lower rate than cache-miss — the API response
    # tells us which is which via usage.prompt_tokens_details.cached_tokens.
    # Override in .env if rates change or you switch model.
    LLM_PRICE_INPUT_CACHED_PER_M_USD: float = float(_get("LLM_PRICE_INPUT_CACHED_PER_M_USD", "0.16") or "0.16")
    LLM_PRICE_INPUT_UNCACHED_PER_M_USD: float = float(_get("LLM_PRICE_INPUT_UNCACHED_PER_M_USD", "0.95") or "0.95")
    LLM_PRICE_OUTPUT_PER_M_USD: float = float(_get("LLM_PRICE_OUTPUT_PER_M_USD", "4.00") or "4.00")
    # USD->GBP fx rate. Default verified May 2026 (1 USD = 0.734 GBP). Currency
    # rates drift; bump in .env occasionally if accuracy matters.
    USD_TO_GBP: float = float(_get("USD_TO_GBP", "0.734") or "0.734")


config = Config()
