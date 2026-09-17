"""Background filesystem scanner used by the GUI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QObject, Signal, Slot

from .config import SUPPORTED_EXTENSIONS
from .database import LibraryDB
from .metadata import read_track


class ScannerWorker(QObject):
    progress = Signal(int, int, str)  # processed, total, current file
    finished = Signal(int)  # number of files visited
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, roots: Iterable[str], db_path: str, cover_dir: str):
        super().__init__()
        self.roots = [os.path.normpath(os.path.abspath(str(root))) for root in roots]
        self.db_path = db_path
        self.cover_dir = Path(cover_dir)
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def _iter_files(self):
        for root in self.roots:
            if not os.path.isdir(root):
                continue
            for current, directories, names in os.walk(root):
                # Avoid wasting time walking hidden cache folders.  The music
                # folder itself is still allowed to be hidden if explicitly
                # selected by the user.
                directories[:] = [d for d in directories if d not in {".git", ".cache", "__pycache__"}]
                for name in names:
                    path = Path(current) / name
                    if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                        yield path

    @Slot()
    def run(self) -> None:
        try:
            db = LibraryDB(self.db_path)
            db.initialize()
            total = sum(1 for _ in self._iter_files())
            if self._cancel_requested:
                self.cancelled.emit()
                return

            processed = 0
            seen: set[str] = set()
            batch: list[dict] = []
            for path in self._iter_files():
                if self._cancel_requested:
                    self.cancelled.emit()
                    return
                normalized = os.path.normpath(str(path.resolve()))
                seen.add(normalized)
                track = read_track(path, self.cover_dir)
                if track:
                    batch.append(track)
                processed += 1
                if len(batch) >= 64:
                    db.upsert_tracks(batch)
                    batch.clear()
                if processed == 1 or processed % 8 == 0 or processed == total:
                    self.progress.emit(processed, total, path.name)

            if batch:
                db.upsert_tracks(batch)
            if not self._cancel_requested:
                db.delete_missing_under_roots(self.roots, seen)
                self.finished.emit(processed)
            else:
                self.cancelled.emit()
        except Exception as exc:  # surface a useful message without killing Qt
            self.failed.emit(f"{type(exc).__name__}: {exc}")
