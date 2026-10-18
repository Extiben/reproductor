"""Modelos de datos de Audius, validados a partir del JSON de la API.

Los nombres de campo siguen el esquema ``track`` de la especificación OpenAPI
oficial (https://api.audius.co/v1/swagger.yaml). Ningún campo opcional se da
por garantizado: si falta o tiene un tipo inesperado se usa un valor neutro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

AUDIUS_WEB_URL = "https://audius.co"
ARTWORK_SIZES = ("150x150", "480x480", "1000x1000")


def _str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    return 0


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class Artwork:
    """Portada con variantes de tamaño y hosts espejo (ver guía *Image Mirrors*)."""

    sizes: dict[str, str] = field(default_factory=dict)
    mirrors: tuple[str, ...] = ()

    @classmethod
    def from_api(cls, raw: Any) -> "Artwork":
        data = _dict(raw)
        sizes = {size: url for size in ARTWORK_SIZES if (url := _str(data.get(size)))}
        mirrors = tuple(m for m in (data.get("mirrors") or []) if isinstance(m, str) and m)
        return cls(sizes=sizes, mirrors=mirrors)

    @property
    def available(self) -> bool:
        return bool(self.sizes)

    def url_for(self, preferred: str = "150x150") -> str:
        """Devuelve la variante pedida o la más cercana disponible."""
        if preferred in self.sizes:
            return self.sizes[preferred]
        for size in ARTWORK_SIZES:
            if size in self.sizes:
                return self.sizes[size]
        return ""

    def candidate_urls(self, preferred: str = "150x150") -> list[str]:
        """URL principal seguida de la misma ruta en cada host espejo."""
        primary = self.url_for(preferred)
        if not primary:
            return []
        urls = [primary]
        parts = urlsplit(primary)
        for mirror in self.mirrors:
            host = urlsplit(mirror)
            if host.netloc and host.netloc != parts.netloc:
                urls.append(urlunsplit((host.scheme or parts.scheme, host.netloc,
                                        parts.path, parts.query, parts.fragment)))
        return urls


@dataclass(frozen=True)
class AudiusTrack:
    id: str
    title: str
    artist: str
    artist_handle: str = ""
    duration: int = 0
    genre: str = ""
    album: str = ""
    permalink: str = ""
    artwork: Artwork = field(default_factory=Artwork)
    is_streamable: bool = False
    is_available: bool = True
    is_stream_gated: bool = False
    can_stream: bool = False

    @classmethod
    def from_api(cls, raw: Any) -> "AudiusTrack | None":
        """Crea una pista a partir del JSON; devuelve ``None`` si no es válido."""
        data = _dict(raw)
        track_id = _str(data.get("id"))
        if not track_id or data.get("is_delete") is True:
            return None
        user = _dict(data.get("user"))
        access = _dict(data.get("access"))
        album = _dict(data.get("album_backlink"))
        is_streamable = data.get("is_streamable") is True
        is_available = data.get("is_available") is not False
        is_gated = data.get("is_stream_gated") is True
        # ``access.stream`` indica si el usuario (anónimo en nuestro caso) puede
        # reproducir la pista; si no viene, se infiere de que no esté restringida.
        access_stream = access.get("stream")
        has_access = access_stream if isinstance(access_stream, bool) else not is_gated
        return cls(
            id=track_id,
            title=_str(data.get("title")) or "Sin título",
            artist=_str(user.get("name")) or _str(user.get("handle")) or "Artista desconocido",
            artist_handle=_str(user.get("handle")),
            duration=_int(data.get("duration")),
            genre=_str(data.get("genre")),
            album=_str(album.get("playlist_name")),
            permalink=_str(data.get("permalink")),
            artwork=Artwork.from_api(data.get("artwork")),
            is_streamable=is_streamable,
            is_available=is_available,
            is_stream_gated=is_gated,
            can_stream=is_streamable and is_available and has_access,
        )

    @property
    def web_url(self) -> str:
        if self.permalink.startswith("http"):
            return self.permalink
        if self.permalink:
            return f"{AUDIUS_WEB_URL}/{self.permalink.lstrip('/')}"
        return ""

    @property
    def duration_label(self) -> str:
        return format_duration(self.duration)

    @property
    def unavailable_reason(self) -> str:
        if not self.is_available:
            return "La pista ya no está disponible en Audius."
        if self.is_stream_gated and not self.can_stream:
            return "Pista con acceso restringido por el artista."
        if not self.is_streamable:
            return "Audius no permite reproducir esta pista en streaming."
        return ""


def format_duration(seconds: int | float) -> str:
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"
