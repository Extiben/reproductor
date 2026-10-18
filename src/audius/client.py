"""Cliente HTTP de solo lectura para la API REST de Audius.

Endpoints usados (especificación oficial https://api.audius.co/v1/swagger.yaml):

* ``GET /tracks/search``             -> ``{"data": [track, ...]}``
* ``GET /tracks/{track_id}``         -> ``{"data": track}``
* ``GET /tracks/{track_id}/stream``  -> con ``no_redirect=true`` devuelve
  ``{"data": "<url firmada de streaming>"}`` en lugar de un 302.

No depende de Tkinter ni del motor de audio: se puede usar y probar por separado.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import (
    AUDIUS_API_BASE_URL,
    AUDIUS_API_KEY,
    AUDIUS_SEARCH_LIMIT,
    AUDIUS_TIMEOUT_SECONDS,
)
from src.audius.models import AudiusTrack

USER_AGENT = "KTOmusic/2.0 (+desktop; python-requests)"
MAX_SEARCH_LIMIT = 50
SEARCH_CACHE_TTL = 300  # segundos
SEARCH_CACHE_SIZE = 64


class AudiusError(Exception):
    """Error base de la integración con Audius (mensaje apto para la UI)."""


class AudiusConnectionError(AudiusError):
    pass


class AudiusRateLimitError(AudiusError):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AudiusNotFoundError(AudiusError):
    pass


class AudiusResponseError(AudiusError):
    pass


class AudiusTrackUnavailableError(AudiusError):
    pass


class AudiusClient:
    def __init__(
        self,
        base_url: str = AUDIUS_API_BASE_URL,
        api_key: str = AUDIUS_API_KEY,
        timeout: float = AUDIUS_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or self._build_session()
        self._search_cache: dict[tuple[str, int, int], tuple[float, list[AudiusTrack]]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        session.headers.update({"Accept": "application/json", "User-Agent": USER_AGENT})
        # Reintentos breves solo ante fallos transitorios del servidor; los 429 no
        # se reintentan automáticamente para no agravar el límite de solicitudes.
        retry = Retry(total=2, connect=2, read=1, backoff_factor=0.6,
                      status_forcelist=(502, 503, 504), allowed_methods=frozenset({"GET"}),
                      respect_retry_after_header=True, raise_on_status=False)
        session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=8))
        return session

    # ------------------------------------------------------------------ API
    def search_tracks(self, query: str, limit: int = AUDIUS_SEARCH_LIMIT,
                      offset: int = 0) -> list[AudiusTrack]:
        """Busca pistas por título o artista."""
        query = " ".join(query.split())
        if not query:
            return []
        limit = max(1, min(int(limit), MAX_SEARCH_LIMIT))
        offset = max(0, int(offset))
        key = (query.casefold(), limit, offset)
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        payload = self._get_json("/tracks/search",
                                 {"query": query, "limit": limit, "offset": offset})
        items = payload.get("data")
        if not isinstance(items, list):
            raise AudiusResponseError("Respuesta de búsqueda inesperada de Audius.")
        tracks = [t for t in (AudiusTrack.from_api(item) for item in items) if t is not None]
        self._cache_put(key, tracks)
        return tracks

    def get_track(self, track_id: str) -> AudiusTrack:
        """Detalles actualizados de una pista."""
        payload = self._get_json(f"/tracks/{self._safe_id(track_id)}")
        track = AudiusTrack.from_api(payload.get("data"))
        if track is None:
            raise AudiusNotFoundError("La pista no existe o fue eliminada.")
        return track

    def get_stream_url(self, track: AudiusTrack | str) -> str:
        """URL de streaming oficial (firmada y temporal: pedirla justo antes de reproducir)."""
        if isinstance(track, AudiusTrack):
            if not track.can_stream:
                raise AudiusTrackUnavailableError(track.unavailable_reason or
                                                  "Esta pista no se puede reproducir.")
            track_id = track.id
        else:
            track_id = track
        params: dict[str, Any] = {"no_redirect": "true"}
        try:
            payload = self._get_json(f"/tracks/{self._safe_id(track_id)}/stream", params)
        except AudiusNotFoundError as exc:
            raise AudiusTrackUnavailableError(
                "Audius no ofrece streaming para esta pista.") from exc
        url = payload.get("data")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise AudiusResponseError("Audius no devolvió una URL de streaming válida.")
        return url

    def close(self) -> None:
        self.session.close()

    # -------------------------------------------------------------- helpers
    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = dict(params or {})
        if self.api_key:
            # ``api_key`` es el parámetro de consulta documentado para apps de terceros.
            params["api_key"] = self.api_key
        url = f"{self.base_url}{path}"
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
        except requests.Timeout as exc:
            raise AudiusConnectionError("Audius tardó demasiado en responder.") from exc
        except requests.ConnectionError as exc:
            raise AudiusConnectionError("No se pudo conectar con Audius. Revisa tu conexión.") from exc
        except requests.RequestException as exc:
            raise AudiusConnectionError(f"Error de red con Audius: {exc}") from exc

        status = response.status_code
        if status == 429:
            retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
            wait = f" Intenta de nuevo en {int(retry_after)} s." if retry_after else ""
            raise AudiusRateLimitError("Demasiadas solicitudes a Audius." + wait, retry_after)
        if status == 404:
            raise AudiusNotFoundError("Recurso no encontrado en Audius.")
        if status in (401, 403):
            raise AudiusTrackUnavailableError("Audius no autoriza el acceso a este contenido.")
        if status >= 400:
            raise AudiusResponseError(f"Audius respondió con error HTTP {status}.")

        try:
            payload = response.json()
        except ValueError as exc:
            raise AudiusResponseError("Audius devolvió una respuesta que no es JSON.") from exc
        if not isinstance(payload, dict):
            raise AudiusResponseError("Formato de respuesta inesperado de Audius.")
        return payload

    @staticmethod
    def _safe_id(track_id: str) -> str:
        track_id = (track_id or "").strip()
        if not track_id or not track_id.isalnum():
            raise AudiusError("Identificador de pista inválido.")
        return track_id

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        try:
            return max(0.0, float(value)) if value else None
        except ValueError:
            return None

    def _cache_get(self, key: tuple[str, int, int]) -> list[AudiusTrack] | None:
        with self._lock:
            entry = self._search_cache.get(key)
            if entry and time.monotonic() - entry[0] < SEARCH_CACHE_TTL:
                return entry[1]
            self._search_cache.pop(key, None)
            return None

    def _cache_put(self, key: tuple[str, int, int], tracks: list[AudiusTrack]) -> None:
        with self._lock:
            if len(self._search_cache) >= SEARCH_CACHE_SIZE:
                oldest = min(self._search_cache, key=lambda k: self._search_cache[k][0])
                self._search_cache.pop(oldest, None)
            self._search_cache[key] = (time.monotonic(), tracks)
