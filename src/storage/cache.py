"""Caché LRU persistente en un único archivo JSON."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.settings import CACHE_DIR, METADATA_FILE, ensure_directories


class CacheManager:
    """Guarda metadata local sin depender de una base de datos."""

    def __init__(self, metadata_file: Path = METADATA_FILE) -> None:
        ensure_directories()
        self.metadata_file = metadata_file

    def get(self, track_id: str) -> dict[str, Any] | None:
        data = self._read()
        track = data["tracks"].get(track_id)
        if track is None:
            return None
        track["last_played_at"] = self._now()
        self._write(data)
        return track

    def save(self, track_id: str, metadata: dict[str, Any]) -> None:
        data = self._read()
        data["tracks"][track_id] = {**metadata, "last_played_at": self._now()}
        self._write(data)

    def audio_path(self, track_id: str) -> Path:
        return CACHE_DIR / f"{track_id}.mp3"

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.metadata_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {"tracks": {}}

    def _write(self, data: dict[str, Any]) -> None:
        self.metadata_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
