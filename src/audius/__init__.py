"""Integración con la API REST pública de Audius (https://api.audius.co/v1)."""

from src.audius.client import (
    AudiusClient,
    AudiusConnectionError,
    AudiusError,
    AudiusNotFoundError,
    AudiusRateLimitError,
    AudiusResponseError,
    AudiusTrackUnavailableError,
)
from src.audius.models import Artwork, AudiusTrack

__all__ = [
    "Artwork",
    "AudiusClient",
    "AudiusConnectionError",
    "AudiusError",
    "AudiusNotFoundError",
    "AudiusRateLimitError",
    "AudiusResponseError",
    "AudiusTrack",
    "AudiusTrackUnavailableError",
]
