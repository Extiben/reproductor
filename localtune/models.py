"""Compact Qt models backed by SQLite queries."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QPixmap

from .database import LibraryDB


def format_duration(value: Any) -> str:
    try:
        total = max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        total = 0
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


class AlbumListModel(QAbstractListModel):
    def __init__(self, db: LibraryDB, parent=None):
        super().__init__(parent)
        self.db = db
        self.rows: list[dict[str, Any]] = []

    def reload(self, search: str = "", limit: int | None = None) -> None:
        rows = self.db.list_albums(search=search, limit=limit)
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        row = self.rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return row.get("album", "Álbum desconocido")
        if role == Qt.ItemDataRole.UserRole:
            return row
        return None

    def album_at(self, row: int) -> dict[str, Any] | None:
        return self.rows[row] if 0 <= row < len(self.rows) else None


class ArtistTableModel(QAbstractTableModel):
    HEADERS = ("Artista", "Álbumes", "Canciones")

    def __init__(self, db: LibraryDB, parent=None):
        super().__init__(parent)
        self.db = db
        self.rows: list[dict[str, Any]] = []

    def reload(self, search: str = "") -> None:
        rows = self.db.list_artists(search=search)
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        row = self.rows[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return row
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if index.column() == 0:
            return row.get("artist", "Artista desconocido")
        if index.column() == 1:
            return str(row.get("album_count", 0))
        if index.column() == 2:
            return str(row.get("track_count", 0))
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def artist_at(self, row: int) -> dict[str, Any] | None:
        return self.rows[row] if 0 <= row < len(self.rows) else None


class TrackTableModel(QAbstractTableModel):
    """Paged song model.

    Only a 250-row window is loaded initially.  QTableView asks for more rows
    as the user approaches the bottom, so a 50,000-track library does not
    become 50,000 QWidget instances or a giant Python list at startup.
    """

    HEADERS = ("Canción", "Artista", "Álbum", "Duración")
    PAGE_SIZE = 250

    def __init__(self, db: LibraryDB, parent=None):
        super().__init__(parent)
        self.db = db
        self.rows: list[dict[str, Any]] = []
        self._search = ""
        self._artist: str | None = None
        self._album: str | None = None
        self._playlist_id: int | None = None
        self._next_offset = 0
        self._complete = True

    def reload(
        self,
        search: str = "",
        artist: str | None = None,
        album: str | None = None,
        playlist_id: int | None = None,
        limit: int | None = None,
    ) -> None:
        # ``limit`` is retained as a friendly API for callers; it controls the
        # first page size, while subsequent pages stay lazy.
        self._search = search
        self._artist = artist
        self._album = album
        self._playlist_id = playlist_id
        page_size = int(limit) if limit and int(limit) > 0 else self.PAGE_SIZE
        page_size = min(max(25, page_size), 500)
        self._page_size = page_size
        self.beginResetModel()
        self.rows = []
        self._next_offset = 0
        self._complete = False
        self.endResetModel()
        self._fetch_page()

    def _fetch_page(self) -> None:
        if self._complete:
            return
        new_rows = self.db.list_tracks(
            search=self._search,
            artist=self._artist,
            album=self._album,
            playlist_id=self._playlist_id,
            limit=self._page_size,
            offset=self._next_offset,
        )
        if not new_rows:
            self._complete = True
            return
        first = len(self.rows)
        last = first + len(new_rows) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self.rows.extend(dict(row) for row in new_rows)
        self.endInsertRows()
        self._next_offset += len(new_rows)
        if len(new_rows) < self._page_size:
            self._complete = True

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def canFetchMore(self, parent: QModelIndex = QModelIndex()) -> bool:
        return not parent.isValid() and not self._complete

    def fetchMore(self, parent: QModelIndex = QModelIndex()) -> None:
        if not parent.isValid():
            self._fetch_page()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        row = self.rows[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return row
        if role == Qt.ItemDataRole.ToolTipRole:
            return row.get("path", "")
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if index.column() == 0:
            return row.get("title", "Sin título")
        if index.column() == 1:
            return row.get("artist", "Artista desconocido")
        if index.column() == 2:
            return row.get("album", "Álbum desconocido")
        if index.column() == 3:
            return format_duration(row.get("duration", 0))
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def track_at(self, row: int) -> dict[str, Any] | None:
        return self.rows[row] if 0 <= row < len(self.rows) else None

    def all_tracks(self) -> list[dict[str, Any]]:
        """Return the active result set for playback, loading later pages on demand."""
        if not self._complete:
            return self.db.list_tracks(
                search=self._search,
                artist=self._artist,
                album=self._album,
                playlist_id=self._playlist_id,
            )
        return list(self.rows)

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self.rows = [dict(row) for row in rows]
        self._search = ""
        self._artist = None
        self._album = None
        self._playlist_id = None
        self._next_offset = len(self.rows)
        self._complete = True
        self.endResetModel()


class OnlineResultModel(QAbstractTableModel):
    """Small non-playable result set returned by the optional online search."""

    HEADERS = ("", "Canción", "Artista", "Álbum")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[dict[str, Any]] = []

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self.rows = [dict(row) for row in rows]
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        row = self.rows[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return row
        if index.column() == 0 and role == Qt.ItemDataRole.DecorationRole:
            path = str(row.get("cover_path") or "")
            if path:
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    return pixmap.scaled(
                        38,
                        38,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if index.column() == 0:
            return ""
        if index.column() == 1:
            return row.get("title", "Sin título")
        if index.column() == 2:
            return row.get("artist", "Artista desconocido")
        if index.column() == 3:
            return row.get("album", "Álbum desconocido")
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None
