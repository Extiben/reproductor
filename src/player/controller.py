"""Estado de reproducción, aislado de la interfaz gráfica.

Motores:

* **Archivos locales**: ``pygame.mixer`` (comportamiento original de ``load`` /
  ``play_pause``).
* **Streaming (Audius)**: VLC mediante ``python-vlc`` si la biblioteca libVLC
  está instalada; reproduce la URL directamente, en streaming real.
  Si VLC no está disponible se usa ``pygame`` como respaldo: el MP3 se descarga
  a un búfer **en memoria** (nunca a disco) y se libera al detener.

Flujo de streaming (pensado para no bloquear la UI)::

    source = player.prepare_stream(url)    # hilo de trabajo (red)
    player.play_source(source, duration)   # hilo principal
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass
from pathlib import Path

import pygame
import requests

STATE_IDLE = "idle"
STATE_LOADING = "loading"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_ENDED = "ended"
STATE_ERROR = "error"

MAX_MEMORY_BUFFER_BYTES = 80 * 1024 * 1024  # límite del respaldo pygame
STREAM_TIMEOUT = (6, 20)  # (conexión, lectura) en segundos


class PlaybackError(Exception):
    """Error de reproducción con mensaje apto para la UI."""


@dataclass
class StreamSource:
    url: str
    buffer: io.BytesIO | None = None  # solo para el respaldo pygame


class PlayerController:
    def __init__(self, prefer_vlc: bool = True) -> None:
        self.current_file: Path | None = None
        self.current_url: str | None = None
        self.paused = False
        self.volume = 0.7
        self.last_error = ""
        self._mixer_ready = self._init_mixer()
        self._vlc_instance = None
        self._vlc_player = None
        self._vlc = None
        if prefer_vlc:
            self._init_vlc()
        self._stream_kind: str | None = None  # "vlc" | "pygame" | None
        self._buffer: io.BytesIO | None = None
        self._duration_hint = 0.0
        self._play_started = 0.0
        self._elapsed_before_pause = 0.0
        self._pygame_was_playing = False

    # ------------------------------------------------------------ backends
    def _init_mixer(self) -> bool:
        try:
            pygame.mixer.init()
            pygame.mixer.music.set_volume(self.volume)
            return True
        except pygame.error as exc:
            self.last_error = f"No se pudo iniciar el audio: {exc}"
            return False

    def _init_vlc(self) -> None:
        try:
            import vlc  # type: ignore[import-not-found]

            instance = vlc.Instance("--no-video", "--quiet", "--network-caching=1500")
            if instance is None:
                return
            self._vlc = vlc
            self._vlc_instance = instance
            self._vlc_player = instance.media_player_new()
            self._vlc_player.audio_set_volume(int(self.volume * 100))
        except Exception:  # ImportError, OSError (libvlc ausente), NameError...
            self._vlc = self._vlc_instance = self._vlc_player = None

    @property
    def stream_backend(self) -> str:
        if self._vlc_player is not None:
            return "VLC (streaming)"
        if self._mixer_ready:
            return "pygame (búfer en memoria)"
        return ""

    @property
    def can_stream(self) -> bool:
        return bool(self.stream_backend)

    # -------------------------------------------------------- local files
    def load(self, audio_file: Path) -> None:
        if not self._mixer_ready:
            raise PlaybackError(self.last_error or "Audio no disponible.")
        self.stop()
        pygame.mixer.music.load(str(audio_file))
        self.current_file = audio_file
        self.paused = False

    def play_pause(self) -> bool:
        if self._stream_kind is not None:
            return self.toggle_pause()
        if self.current_file is None or not self._mixer_ready:
            return False
        if self.paused:
            pygame.mixer.music.unpause()
        elif pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
        else:
            pygame.mixer.music.play()
        self.paused = not self.paused if pygame.mixer.music.get_busy() else False
        return True

    # ------------------------------------------------------------ streaming
    def prepare_stream(self, url: str) -> StreamSource:
        """Valida la URL y, si hace falta, llena el búfer. Seguro en hilos de trabajo."""
        if not self.can_stream:
            raise PlaybackError("No hay un motor de audio disponible para streaming.")
        if self._vlc_player is not None:
            self._probe(url)
            return StreamSource(url=url)
        return StreamSource(url=url, buffer=self._download_to_memory(url))

    def play_source(self, source: StreamSource, duration_hint: float = 0.0) -> None:
        """Detiene lo anterior y reproduce la nueva fuente. Llamar en el hilo principal."""
        self.stop()
        self._duration_hint = float(duration_hint or 0)
        self.last_error = ""
        if self._vlc_player is not None and source.buffer is None:
            media = self._vlc_instance.media_new(source.url)
            self._vlc_player.set_media(media)
            media.release()
            self._vlc_player.audio_set_volume(int(self.volume * 100))
            if self._vlc_player.play() == -1:
                raise PlaybackError("VLC no pudo abrir el stream.")
            self._stream_kind = "vlc"
        elif source.buffer is not None and self._mixer_ready:
            try:
                source.buffer.seek(0)
                pygame.mixer.music.load(source.buffer, "mp3")
                pygame.mixer.music.set_volume(self.volume)
                pygame.mixer.music.play()
            except pygame.error as exc:
                raise PlaybackError(f"Formato de audio no soportado: {exc}") from exc
            self._buffer = source.buffer
            self._stream_kind = "pygame"
            self._pygame_was_playing = True
            self._play_started = time.monotonic()
            self._elapsed_before_pause = 0.0
        else:
            raise PlaybackError("No hay un motor de audio disponible para streaming.")
        self.current_url = source.url
        self.current_file = None
        self.paused = False

    def pause(self) -> None:
        if self._stream_kind == "vlc":
            self._vlc_player.set_pause(1)
        elif self._stream_kind == "pygame" and not self.paused:
            pygame.mixer.music.pause()
            self._elapsed_before_pause += time.monotonic() - self._play_started
        else:
            return
        self.paused = True

    def resume(self) -> None:
        if self._stream_kind == "vlc":
            self._vlc_player.set_pause(0)
        elif self._stream_kind == "pygame" and self.paused:
            pygame.mixer.music.unpause()
            self._play_started = time.monotonic()
        else:
            return
        self.paused = False

    def toggle_pause(self) -> bool:
        if self._stream_kind is None:
            return False
        state = self.state()
        if state == STATE_ENDED:
            return False
        if self.paused:
            self.resume()
        else:
            self.pause()
        return True

    def state(self) -> str:
        if self._stream_kind == "vlc":
            vlc = self._vlc
            current = self._vlc_player.get_state()
            if current in (vlc.State.Opening, vlc.State.Buffering):
                return STATE_LOADING
            if current == vlc.State.Playing:
                return STATE_PLAYING
            if current == vlc.State.Paused:
                return STATE_PAUSED
            if current == vlc.State.Ended:
                return STATE_ENDED
            if current == vlc.State.Error:
                self.last_error = "VLC no pudo reproducir el stream."
                return STATE_ERROR
            return STATE_IDLE
        if self._stream_kind == "pygame":
            if self.paused:
                return STATE_PAUSED
            if pygame.mixer.music.get_busy():
                return STATE_PLAYING
            return STATE_ENDED if self._pygame_was_playing else STATE_IDLE
        return STATE_IDLE

    def position(self) -> float:
        """Segundos reproducidos de la pista actual."""
        if self._stream_kind == "vlc":
            return max(0, self._vlc_player.get_time()) / 1000
        if self._stream_kind == "pygame":
            running = 0.0 if self.paused else time.monotonic() - self._play_started
            value = self._elapsed_before_pause + running
            return min(value, self._duration_hint) if self._duration_hint else value
        return 0.0

    def length(self) -> float:
        if self._stream_kind == "vlc":
            ms = self._vlc_player.get_length()
            if ms and ms > 0:
                return ms / 1000
        return self._duration_hint

    def seek(self, seconds: float) -> None:
        if self._stream_kind == "vlc":
            self._vlc_player.set_time(int(seconds * 1000))
        elif self._stream_kind == "pygame":
            if self._buffer:
                try:
                    pygame.mixer.music.set_pos(seconds)
                    self._elapsed_before_pause = seconds
                    if not self.paused:
                        self._play_started = time.monotonic()
                except pygame.error:
                    # set_pos could fail depending on SDL/format, try play(start=)
                    try:
                        pygame.mixer.music.play(0, seconds)
                        if self.paused:
                            pygame.mixer.music.pause()
                        self._elapsed_before_pause = seconds
                        self._play_started = time.monotonic()
                    except pygame.error:
                        pass

    # ---------------------------------------------------------- common
    def set_volume(self, value: float) -> None:
        self.volume = max(0.0, min(1.0, value))
        if self._mixer_ready:
            pygame.mixer.music.set_volume(self.volume)
        if self._vlc_player is not None:
            self._vlc_player.audio_set_volume(int(self.volume * 100))

    def stop(self) -> None:
        if self._vlc_player is not None:
            self._vlc_player.stop()
        if self._mixer_ready:
            pygame.mixer.music.stop()
            if self._buffer is not None:
                try:
                    pygame.mixer.music.unload()
                except pygame.error:
                    pass
        if self._buffer is not None:
            self._buffer.close()
        self._buffer = None
        self._stream_kind = None
        self._pygame_was_playing = False
        self.current_url = None
        self.paused = False

    def shutdown(self) -> None:
        self.stop()
        if self._vlc_player is not None:
            self._vlc_player.release()
        if self._vlc_instance is not None:
            self._vlc_instance.release()
        self._vlc_player = self._vlc_instance = None

    # ------------------------------------------------------------ network
    @staticmethod
    def _probe(url: str) -> None:
        """Pide 2 bytes con Range para verificar que el stream responde."""
        try:
            with requests.get(url, headers={"Range": "bytes=0-1"}, stream=True,
                              timeout=STREAM_TIMEOUT) as response:
                PlayerController._check_audio_response(response)
        except requests.RequestException as exc:
            raise PlaybackError("No se pudo conectar con el servidor de audio.") from exc

    @staticmethod
    def _download_to_memory(url: str) -> io.BytesIO:
        buffer = io.BytesIO()
        try:
            with requests.get(url, stream=True, timeout=STREAM_TIMEOUT) as response:
                PlayerController._check_audio_response(response)
                declared = int(response.headers.get("Content-Length") or 0)
                if declared > MAX_MEMORY_BUFFER_BYTES:
                    raise PlaybackError("Pista demasiado larga para reproducir sin VLC.")
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    buffer.write(chunk)
                    if buffer.tell() > MAX_MEMORY_BUFFER_BYTES:
                        raise PlaybackError("La pista es demasiado grande para el búfer en memoria.")
        except requests.RequestException as exc:
            buffer.close()
            raise PlaybackError("Se interrumpió la descarga del stream.") from exc
        except PlaybackError:
            buffer.close()
            raise
        if buffer.tell() == 0:
            raise PlaybackError("El servidor de audio devolvió una respuesta vacía.")
        buffer.seek(0)
        return buffer

    @staticmethod
    def _check_audio_response(response: requests.Response) -> None:
        if response.status_code in (401, 403):
            raise PlaybackError("Audius no autoriza la reproducción de esta pista.")
        if response.status_code == 404:
            raise PlaybackError("El archivo de audio no está disponible.")
        if response.status_code >= 400:
            raise PlaybackError(f"El servidor de audio respondió HTTP {response.status_code}.")
        content_type = response.headers.get("Content-Type", "").lower()
        if content_type and not content_type.startswith(("audio/", "application/octet-stream")):
            raise PlaybackError("El stream no devolvió contenido de audio.")
