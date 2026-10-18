"""Carga asíncrona de portadas con caché en memoria y reintento por espejos usando PIL y CTkImage."""

from __future__ import annotations

import io
import threading
from collections import OrderedDict
from typing import Callable
import requests
from PIL import Image
import customtkinter as ctk

from src.audius.models import Artwork
from src.ui import styles
from src.ui.background import BackgroundRunner

IMAGE_TIMEOUT = (4, 8)
MAX_IMAGE_BYTES = 4 * 1024 * 1024
CACHE_SIZE = 300

PhotoCallback = Callable[[ctk.CTkImage], None]


class ImageLoader:
    def __init__(self, runner: BackgroundRunner) -> None:
        self._runner = runner
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "KTOmusic/2.0"})
        self._cache: OrderedDict[str, ctk.CTkImage] = OrderedDict()
        self._pending: dict[str, list[PhotoCallback]] = {}
        self._failed: set[str] = set()
        self._decode_lock = threading.Lock()

    def placeholder(self, size: int) -> str:
        return "♫"

    def load(self, artwork: Artwork, size: int, callback: PhotoCallback) -> None:
        """Entrega la portada (o nada si falla) a ``callback`` en el hilo principal."""
        variant = "150x150" if size <= 150 else "480x480"
        urls = artwork.candidate_urls(variant)
        if not urls:
            return
        key = f"{urls[0]}@{size}"
        
        if key in self._cache:
            self._cache.move_to_end(key)
            callback(self._cache[key])
            return
        if key in self._failed:
            return
        if key in self._pending:
            self._pending[key].append(callback)
            return
            
        self._pending[key] = [callback]
        self._runner.submit(self._fetch_image, urls, size,
                            on_success=lambda data: self._deliver(key, data, size),
                            on_error=lambda _exc: self._fail(key))

    # Hilo de trabajo -----------------------------------------------------
    def _fetch_image(self, urls: list[str], size: int) -> bytes:
        last_error: Exception | None = None
        for url in urls:
            try:
                response = self._session.get(url, timeout=IMAGE_TIMEOUT)
                if response.status_code != 200 or not response.content:
                    raise ValueError(f"HTTP {response.status_code}")
                if len(response.content) > MAX_IMAGE_BYTES:
                    raise ValueError("imagen demasiado grande")
                return response.content
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
        raise RuntimeError(f"Portada no disponible: {last_error}")

    # Hilo principal -------------------------------------------------------
    def _deliver(self, key: str, raw_bytes: bytes, size: int) -> None:
        try:
            pil_image = Image.open(io.BytesIO(raw_bytes))
            # Crop to square if needed, or just let CTkImage scale it
            ctk_img = ctk.CTkImage(light_image=pil_image, size=(size, size))
            
            self._cache[key] = ctk_img
            if len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
                
            for callback in self._pending.pop(key, []):
                callback(ctk_img)
        except Exception:
            self._fail(key)

    def _fail(self, key: str) -> None:
        self._failed.add(key)
        self._pending.pop(key, None)
