"""Thin QMediaPlayer controller with a small in-memory playback queue."""

from __future__ import annotations

import random
from typing import Any

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class PlaybackController(QObject):
    currentChanged = Signal(object)
    positionChanged = Signal(int, int)  # position, duration in milliseconds
    playingChanged = Signal(bool)
    queueChanged = Signal()
    errorMessage = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.player.setAudioOutput(self.output)
        self.output.setVolume(0.82)

        self.queue: list[dict[str, Any]] = []
        self.index = -1
        self.current: dict[str, Any] | None = None
        self.shuffle = False
        self.repeat_mode = "none"  # none, all, one

        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.errorOccurred.connect(self._on_error)

    @Slot()
    def play_pause(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            return
        if self.current is None and self.queue:
            self.index = max(0, min(self.index, len(self.queue) - 1))
            self._load_current(play=True)
        else:
            self.player.play()

    def play_tracks(self, tracks: list[dict[str, Any]], index: int = 0) -> None:
        if not tracks:
            return
        self.queue = [dict(track) for track in tracks]
        self.index = max(0, min(int(index), len(self.queue) - 1))
        self.queueChanged.emit()
        self._load_current(play=True)

    def play_track(self, track: dict[str, Any]) -> None:
        """Play a single track while retaining the existing queue when possible."""
        track = dict(track)
        for position, queued in enumerate(self.queue):
            if queued.get("id") == track.get("id") and track.get("id") is not None:
                self.index = position
                break
        else:
            self.queue = [track]
            self.index = 0
            self.queueChanged.emit()
        self._load_current(play=True)

    def enqueue_next(self, track: dict[str, Any]) -> None:
        track = dict(track)
        if not self.queue:
            self.queue = [track]
            self.index = 0
        else:
            insert_at = self.index + 1 if self.index >= 0 else len(self.queue)
            self.queue.insert(insert_at, track)
        self.queueChanged.emit()

    def append_to_queue(self, tracks: list[dict[str, Any]]) -> None:
        if tracks:
            self.queue.extend(dict(track) for track in tracks)
            if self.index < 0:
                self.index = 0
            self.queueChanged.emit()

    def remove_from_queue(self, index: int) -> None:
        if not (0 <= index < len(self.queue)):
            return
        if index == self.index and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            return
        self.queue.pop(index)
        if index < self.index:
            self.index -= 1
        elif index == self.index:
            self.index = min(self.index, len(self.queue) - 1)
        self.queueChanged.emit()

    @Slot()
    def clear_upcoming(self) -> None:
        """Keep the current item playing and remove everything after it."""
        if self.current is not None and 0 <= self.index < len(self.queue):
            self.queue = [dict(self.current)]
            self.index = 0
        else:
            self.queue = []
            self.index = -1
        self.queueChanged.emit()

    @Slot()
    def previous(self) -> None:
        if not self.queue:
            return
        if self.player.position() > 4000:
            self.player.setPosition(0)
            return
        if self.index > 0:
            self.index -= 1
        elif self.repeat_mode == "all":
            self.index = len(self.queue) - 1
        else:
            self.player.setPosition(0)
            return
        self._load_current(play=True)

    @Slot()
    def next(self) -> None:
        if not self.queue:
            return
        if self.repeat_mode == "one":
            self.player.setPosition(0)
            self.player.play()
            return

        if self.shuffle and len(self.queue) > 1:
            candidates = [n for n in range(len(self.queue)) if n != self.index]
            self.index = random.choice(candidates)
        else:
            self.index += 1
            if self.index >= len(self.queue):
                if self.repeat_mode == "all":
                    self.index = 0
                else:
                    self.index = len(self.queue) - 1
                    self.player.stop()
                    self.playingChanged.emit(False)
                    return
        self._load_current(play=True)

    def set_position(self, milliseconds: int) -> None:
        self.player.setPosition(max(0, int(milliseconds)))

    def set_volume(self, value: int) -> None:
        self.output.setVolume(max(0.0, min(1.0, int(value) / 100.0)))

    def toggle_shuffle(self) -> bool:
        self.shuffle = not self.shuffle
        self.queueChanged.emit()
        return self.shuffle

    def toggle_repeat(self) -> str:
        self.repeat_mode = {
            "none": "all",
            "all": "one",
            "one": "none",
        }[self.repeat_mode]
        self.queueChanged.emit()
        return self.repeat_mode

    def _load_current(self, play: bool) -> None:
        if not (0 <= self.index < len(self.queue)):
            return
        self.current = dict(self.queue[self.index])
        self.currentChanged.emit(self.current)
        path = str(self.current.get("path", ""))
        if not path:
            self.errorMessage.emit("La pista no tiene una ruta válida")
            return
        self.player.setSource(QUrl.fromLocalFile(path))
        if play:
            self.player.play()

    def _on_position(self, position: int) -> None:
        self.positionChanged.emit(int(position), int(self.player.duration()))

    def _on_duration(self, duration: int) -> None:
        self.positionChanged.emit(int(self.player.position()), int(duration))

    def _on_state(self, state: QMediaPlayer.PlaybackState) -> None:
        self.playingChanged.emit(state == QMediaPlayer.PlaybackState.PlayingState)

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next()

    def _on_error(self, _error: QMediaPlayer.Error, error_string: str) -> None:
        if error_string:
            self.errorMessage.emit(error_string)

    def queue_snapshot(self) -> list[dict[str, Any]]:
        return [dict(track) for track in self.queue]
