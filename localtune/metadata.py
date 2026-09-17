"""Metadata and embedded-cover extraction with a tiny on-disk thumbnail cache."""

from __future__ import annotations

import base64
import hashlib
import os
import re
from pathlib import Path
from typing import Any

from mutagen import File
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


_TRACK_NUMBER_RE = re.compile(r"^\s*(\d+)")


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "text"):
        value = getattr(value, "text")
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="replace")
        except Exception:
            return ""
    return " ".join(str(value).replace("\x00", "").split()).strip()


def _tag_text(tags: Any, keys: tuple[str, ...], fallback: str) -> str:
    if tags:
        for key in keys:
            try:
                if key in tags:
                    value = _text_value(tags.get(key))
                    if value:
                        return value
            except Exception:
                continue
    return fallback


def _track_number(tags: Any) -> int:
    value = _tag_text(tags, ("tracknumber", "track", "TRCK"), "")
    match = _TRACK_NUMBER_RE.match(value)
    return int(match.group(1)) if match else 0


def _embedded_cover(audio: Any) -> bytes | None:
    """Get the first useful embedded image for ID3, FLAC or Vorbis files."""
    try:
        pictures = getattr(audio, "pictures", None)
        if pictures:
            data = getattr(pictures[0], "data", None)
            if data:
                return bytes(data)
    except Exception:
        pass

    tags = getattr(audio, "tags", None)
    if not tags:
        return None

    # MP3/ID3 APIC frames.
    try:
        for key in tags.keys():
            if str(key).upper().startswith("APIC"):
                data = getattr(tags[key], "data", None)
                if data:
                    return bytes(data)
    except Exception:
        pass

    # Ogg Vorbis/Opus stores FLAC picture blocks as base64 text.
    for key in ("metadata_block_picture", "METADATA_BLOCK_PICTURE"):
        try:
            values = tags.get(key)
            if values:
                if not isinstance(values, (list, tuple)):
                    values = [values]
                for value in values:
                    decoded = base64.b64decode(_text_value(value), validate=False)
                    if decoded:
                        # A FLAC picture block has a small binary header.  A
                        # QImage cannot read that wrapper, so parse the image
                        # payload using mutagen's Picture when available.
                        try:
                            from mutagen.flac import Picture

                            picture = Picture(decoded)
                            if picture.data:
                                return bytes(picture.data)
                        except Exception:
                            # Some files put the image bytes directly in the
                            # field; retaining the decoded bytes is harmless.
                            return decoded
        except Exception:
            continue

    # A few containers expose MP4-style cover values through a free-form tag.
    for key in ("covr", "coverart", "cover_art"):
        try:
            values = tags.get(key)
            if values:
                if not isinstance(values, (list, tuple)):
                    values = [values]
                candidate = values[0]
                if isinstance(candidate, bytes):
                    return candidate
        except Exception:
            continue
    return None


def cache_cover(data: bytes | None, cache_dir: Path) -> str | None:
    """Write a 320px JPEG thumbnail once and return its absolute path."""
    if not data:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(data).hexdigest()[:24]
    destination = cache_dir / f"{digest}.jpg"
    if destination.exists() and destination.stat().st_size > 0:
        return str(destination)

    image = QImage()
    if not image.loadFromData(data):
        return None
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    image = image.scaled(320, 320, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    if image.save(str(destination), "JPG", 82):
        return str(destination)
    return None


def read_track(path: Path, cache_dir: Path) -> dict[str, Any] | None:
    """Read one supported audio file.  Invalid files are skipped by caller."""
    try:
        audio = File(str(path), easy=False)
    except Exception:
        return None
    if audio is None:
        return None

    tags = getattr(audio, "tags", None)
    stem = path.stem.replace("_", " ").strip() or "Sin título"
    title = _tag_text(tags, ("title", "TIT2"), stem)
    artist = _tag_text(tags, ("artist", "TPE1"), "Artista desconocido")
    album = _tag_text(tags, ("album", "TALB"), "Álbum desconocido")
    album_artist = _tag_text(
        tags,
        ("albumartist", "album artist", "TPE2", "TXXX:ALBUMARTIST"),
        artist,
    )
    genre = _tag_text(tags, ("genre", "TCON"), "")
    duration = 0.0
    try:
        duration = float(getattr(getattr(audio, "info", None), "length", 0.0) or 0.0)
    except Exception:
        pass

    return {
        "path": str(path.resolve()),
        "title": title,
        "artist": artist,
        "album": album,
        "album_artist": album_artist,
        "genre": genre,
        "track_number": _track_number(tags),
        "duration": duration,
        "cover_path": cache_cover(_embedded_cover(audio), cache_dir),
        "mtime": os.path.getmtime(path),
    }
