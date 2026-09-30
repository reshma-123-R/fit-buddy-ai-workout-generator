"""Central configuration for FitBuddy.

Values come from environment variables, optionally loaded from a `.env` file in
the project root. Real environment variables always win over `.env` values.
Importing this module never touches the network, so it is always safe.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

load_dotenv(PROJECT_ROOT / ".env", override=False)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


# --- Database ---------------------------------------------------------------
# Default: a SQLite file called fitbuddy.db in the project root (auto-created).
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{(PROJECT_ROOT / 'fitbuddy.db').as_posix()}"

# --- Gemini -----------------------------------------------------------------
# Model names change over time (Gemini 1.5 and 2.0 are already retired), so they
# are configurable. See https://ai.google.dev/gemini-api/docs/models
GEMINI_PRO_MODEL = os.getenv("GEMINI_PRO_MODEL") or "gemini-3.1-pro-preview"   # workout plans
GEMINI_FLASH_MODEL = os.getenv("GEMINI_FLASH_MODEL") or "gemini-3.8-flash"     # nutrition tips + fallback
GEMINI_TIMEOUT_SECONDS = _int_env("GEMINI_TIMEOUT_SECONDS", 90)

_PLACEHOLDER_KEYS = {"", "your_api_key_here", "your-api-key-here", "changeme"}


def get_gemini_api_key() -> str | None:
    """Return the API key, or None when it is missing or still the .env.example placeholder."""
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    return None if key.lower() in _PLACEHOLDER_KEYS else key
