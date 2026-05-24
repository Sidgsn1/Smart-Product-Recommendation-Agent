"""
Shared Gemini configuration for LangChain and CrewAI.

Loads GEMINI_API_KEY from the project-root .env file (via python-dotenv).
Provides one lazy singleton LangChain chat model and one CrewAI LLM
using the same model name and API key — never hardcoded in source.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Project root: parent of src/ — .env is always loaded from here, not cwd.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

# Defaults can be overridden in .env
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_OUTPUT_TOKENS = 400

_langchain_llm: Any = None
_crewai_llm: Any = None
_env_loaded = False


def load_project_env(*, override: bool = False) -> bool:
    """
    Load environment variables from the project-root .env file.

    Safe to call multiple times. Returns True when .env exists and was read.
    """
    global _env_loaded

    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=override)
        _env_loaded = True
        logger.debug("Loaded environment from %s", _ENV_FILE)
        return True

    # Fallback: allow a .env in the current working directory (e.g. tests).
    load_dotenv(override=override)
    _env_loaded = True
    logger.debug("No project .env at %s; tried cwd fallback", _ENV_FILE)
    return False


# Load .env once when this module is imported.
load_project_env()


def get_gemini_api_key() -> Optional[str]:
    """Return Gemini API key from environment, or None if missing."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        logger.debug("GEMINI_API_KEY is not set; using deterministic fallback summaries.")
    return key or None


def get_gemini_model_name() -> str:
    """Return Gemini model id (without provider prefix)."""
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def is_gemini_configured() -> bool:
    """True when GEMINI_API_KEY is set."""
    return get_gemini_api_key() is not None


def get_gemini_llm() -> Optional[Any]:
    """
    Shared LangChain Gemini chat model (langchain-google-genai).

    Returns None if the API key is missing or the package cannot be loaded.
    """
    global _langchain_llm

    api_key = get_gemini_api_key()
    if not api_key:
        return None

    if _langchain_llm is not None:
        return _langchain_llm

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        logger.warning("langchain-google-genai is not installed; LangChain Gemini unavailable.")
        return None

    _langchain_llm = ChatGoogleGenerativeAI(
        model=get_gemini_model_name(),
        google_api_key=api_key,
        temperature=DEFAULT_TEMPERATURE,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
    )
    logger.debug("LangChain Gemini client initialized (model=%s)", get_gemini_model_name())
    return _langchain_llm


def get_crewai_llm() -> Optional[Any]:
    """
    Shared CrewAI LLM pointed at Gemini (same key/model as LangChain config).

    All CrewAI agents must use this singleton — do not create separate LLM instances.
    """
    global _crewai_llm

    api_key = get_gemini_api_key()
    if not api_key:
        return None

    if _crewai_llm is not None:
        return _crewai_llm

    try:
        from crewai import LLM
    except ImportError:
        logger.warning("crewai is not installed; CrewAI Gemini unavailable.")
        return None

    model_name = get_gemini_model_name()
    # CrewAI expects provider/model for Gemini.
    crew_model = model_name if model_name.startswith("gemini/") else f"gemini/{model_name}"

    _crewai_llm = LLM(
        model=crew_model,
        api_key=api_key,
        temperature=DEFAULT_TEMPERATURE,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
    )
    logger.debug("CrewAI Gemini LLM initialized (model=%s)", crew_model)
    return _crewai_llm


def reset_gemini_llm_cache() -> None:
    """
    Clear cached LLM instances.

    Call after updating GEMINI_API_KEY at runtime (e.g. console prompt in main.py)
    so the next get_gemini_llm / get_crewai_llm picks up the new key.
    """
    global _langchain_llm, _crewai_llm
    _langchain_llm = None
    _crewai_llm = None
    logger.debug("Gemini LLM cache cleared")


def _resolve_secret(value: Any) -> Optional[str]:
    """Extract plain string from env value or pydantic SecretStr."""
    if value is None:
        return None
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        text = getter()
    else:
        text = value
    text = str(text).strip()
    return text or None


def verify_shared_gemini_config() -> Dict[str, Any]:
    """
    Verify .env key loading and that LangChain + CrewAI share one configuration.

    Never returns the raw API key — only booleans and model metadata.
    """
    api_key = get_gemini_api_key()
    langchain_llm = get_gemini_llm()
    crewai_llm = get_crewai_llm()

    langchain_key_match = False
    if langchain_llm is not None and api_key:
        lc_key = _resolve_secret(getattr(langchain_llm, "google_api_key", None))
        langchain_key_match = lc_key == api_key

    crewai_key_match = False
    if crewai_llm is not None and api_key:
        cr_key = _resolve_secret(getattr(crewai_llm, "api_key", None))
        crewai_key_match = cr_key == api_key

    return {
        "env_file_exists": _ENV_FILE.exists(),
        "env_file_path": str(_ENV_FILE),
        "gemini_api_key_set": api_key is not None,
        "gemini_model": get_gemini_model_name(),
        "langchain_llm_ready": langchain_llm is not None,
        "crewai_llm_ready": crewai_llm is not None,
        "langchain_uses_env_key": langchain_key_match,
        "crewai_uses_env_key": crewai_key_match,
        "shared_config_ok": (
            api_key is not None
            and langchain_llm is not None
            and crewai_llm is not None
            and langchain_key_match
            and crewai_key_match
        ),
    }
