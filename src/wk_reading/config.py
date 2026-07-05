"""Configuration: loads the WaniKani token and resolves paths."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = two levels up from this file (src/wk_reading/config.py -> project/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "wk_reading.sqlite3"

# WaniKani API v2. The Revision header pins the response schema.
WK_API_BASE = "https://api.wanikani.com/v2"
WK_REVISION = "20170710"

load_dotenv(PROJECT_ROOT / ".env")


def get_token() -> str:
    """Return the WaniKani token from the environment, or raise a clear error."""
    token = os.environ.get("WK_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "WK_TOKEN is not set. Copy .env.example to .env and add your "
            "WaniKani personal access token."
        )
    return token


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
