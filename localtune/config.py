"""Paths and small application-wide constants."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "LocalTune"
APP_VERSION = "0.1.0"
SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".ogg", ".oga"}


def _default_data_dir() -> Path:
    """Return a platform-appropriate writable data directory."""
    override = os.environ.get("LOCALTUNE_DATA_DIR")
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / APP_NAME


DATA_DIR = _default_data_dir()
DB_PATH = DATA_DIR / "library.sqlite3"
COVERS_DIR = DATA_DIR / "covers"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
