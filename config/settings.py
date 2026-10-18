"""Rutas, límites y configuración de entorno de la aplicación."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
TEMP_DIR = CACHE_DIR / "temp"
METADATA_FILE = DATA_DIR / "metadata.json"
LOG_DIR = PROJECT_ROOT / "logs"

CACHE_LIMIT_MB = int(os.getenv("KTO_CACHE_LIMIT_MB", "2048"))
SPOTIFY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None

# Audius: las lecturas públicas funcionan sin credenciales; la API key es opcional
# (mayor límite de solicitudes y acceso a pistas restringidas a ciertas keys).
AUDIUS_API_BASE_URL = os.getenv("AUDIUS_API_BASE_URL", "https://api.audius.co/v1").rstrip("/")
AUDIUS_API_KEY = os.getenv("AUDIUS_API_KEY", "").strip()
AUDIUS_SEARCH_LIMIT = int(os.getenv("AUDIUS_SEARCH_LIMIT", "20"))
AUDIUS_TIMEOUT_SECONDS = float(os.getenv("AUDIUS_TIMEOUT_SECONDS", "10"))


def ensure_directories() -> None:
    """Crea los directorios y el archivo de metadata requeridos al iniciar."""
    for directory in (CACHE_DIR, TEMP_DIR, LOG_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    if not METADATA_FILE.exists():
        METADATA_FILE.write_text('{"tracks": {}}\n', encoding="utf-8")
