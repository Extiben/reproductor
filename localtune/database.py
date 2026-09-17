"""Small SQLite data layer.

The UI never keeps the complete music library in widgets.  Models ask this
class for compact rows, while the database owns the persistent library and
playlists.  Connections are intentionally short-lived so the scanner can run
in its own Qt thread without sharing a sqlite connection with the GUI thread.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Iterable


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT NOT NULL,
    album_artist TEXT NOT NULL DEFAULT '',
    genre TEXT NOT NULL DEFAULT '',
    track_number INTEGER NOT NULL DEFAULT 0,
    duration REAL NOT NULL DEFAULT 0,
    cover_path TEXT,
    mtime REAL NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tracks_path ON tracks(path);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (playlist_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_playlist_tracks_position
    ON playlist_tracks(playlist_id, position);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class LibraryDB:
    """SQLite access object whose methods are safe to call from Qt threads."""

    def __init__(self, path: Path | str):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._session() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.executescript(SCHEMA)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    @staticmethod
    def _contains(value: str) -> str:
        # Search is literal rather than allowing a user-entered % or _ to
        # turn into a wildcard.  SQLite's NOCASE covers ASCII well and the
        # UI remains instant for normal local-library queries.
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._session() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return row[0]

    def set_setting(self, key: str, value: Any) -> None:
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        with self._session() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def upsert_tracks(self, tracks: Iterable[dict[str, Any]]) -> None:
        rows = [
            (
                str(track["path"]),
                str(track.get("title") or "Sin título"),
                str(track.get("artist") or "Artista desconocido"),
                str(track.get("album") or "Álbum desconocido"),
                str(track.get("album_artist") or ""),
                str(track.get("genre") or ""),
                int(track.get("track_number") or 0),
                float(track.get("duration") or 0),
                track.get("cover_path"),
                float(track.get("mtime") or 0),
            )
            for track in tracks
        ]
        if not rows:
            return
        sql = """
        INSERT INTO tracks(
            path, title, artist, album, album_artist, genre,
            track_number, duration, cover_path, mtime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            title = excluded.title,
            artist = excluded.artist,
            album = excluded.album,
            album_artist = excluded.album_artist,
            genre = excluded.genre,
            track_number = excluded.track_number,
            duration = excluded.duration,
            cover_path = excluded.cover_path,
            mtime = excluded.mtime
        """
        with self._session() as conn:
            conn.executemany(sql, rows)

    def delete_missing_under_roots(self, roots: Iterable[str], seen_paths: set[str]) -> int:
        """Remove database entries below scanned roots that no longer exist."""
        removed = 0
        normalized_roots = [os.path.normpath(os.path.abspath(root)) for root in roots]
        with self._session() as conn:
            for root in normalized_roots:
                prefix = root + os.sep
                rows = conn.execute(
                    "SELECT id, path FROM tracks WHERE path = ? OR path LIKE ?",
                    (root, prefix + "%"),
                ).fetchall()
                stale_ids = [row[0] for row in rows if os.path.normpath(row[1]) not in seen_paths]
                if stale_ids:
                    placeholders = ",".join("?" for _ in stale_ids)
                    cur = conn.execute(
                        f"DELETE FROM tracks WHERE id IN ({placeholders})", stale_ids
                    )
                    removed += cur.rowcount
        return removed

    def count_tracks(self) -> int:
        with self._session() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0])

    def tracks_for_online_lookup(self, limit: int = 500) -> list[dict[str, Any]]:
        """Return compact rows used by the optional online metadata lookup."""
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT id, title, artist, album, cover_path
                FROM tracks
                ORDER BY
                    CASE WHEN cover_path IS NULL OR cover_path = '' THEN 0 ELSE 1 END,
                    lower(artist) COLLATE NOCASE, lower(album) COLLATE NOCASE,
                    track_number, lower(title) COLLATE NOCASE
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
            return [dict(row) for row in rows]

    def tracks_without_covers(self, limit: int = 500) -> list[dict[str, Any]]:
        """Backward-compatible helper for callers that only need missing art."""
        return [
            row for row in self.tracks_for_online_lookup(limit=limit)
            if not row.get("cover_path")
        ]

    def apply_online_album_match(
        self,
        artist: str,
        album: str,
        remote_artist: str,
        remote_album: str,
        cover_path: str | None,
    ) -> int:
        """Enrich the local DB without modifying the user's audio files.

        The remote artist/album are only applied to the local index after a
        strong search match.  Existing local artwork is preserved; the online
        image fills only missing artwork slots.
        """
        new_artist = remote_artist.strip() or artist
        new_album = remote_album.strip() or album
        with self._session() as conn:
            cur = conn.execute(
                """
                UPDATE tracks
                SET artist = ?,
                    album = ?,
                    album_artist = ?,
                    cover_path = CASE
                        WHEN (cover_path IS NULL OR cover_path = '') AND ? IS NOT NULL
                        THEN ?
                        ELSE cover_path
                    END
                WHERE artist = ? AND album = ?
                """,
                (new_artist, new_album, new_artist, cover_path, cover_path, artist, album),
            )
            return int(cur.rowcount)

    def list_albums(self, search: str = "", limit: int | None = None) -> list[dict[str, Any]]:
        expression = "COALESCE(NULLIF(album_artist, ''), NULLIF(artist, ''), 'Artista desconocido')"
        sql = f"""
            SELECT
                MIN(id) AS id,
                album,
                {expression} AS artist,
                MIN(cover_path) AS cover_path,
                COUNT(*) AS track_count
            FROM tracks
            WHERE album <> ''
        """
        params: list[Any] = []
        if search.strip():
            needle = self._contains(search.strip())
            sql += f" AND (album COLLATE NOCASE LIKE ? ESCAPE '\\' OR ({expression}) COLLATE NOCASE LIKE ? ESCAPE '\\')"
            params.extend([needle, needle])
        sql += f" GROUP BY album, {expression} ORDER BY lower(album) COLLATE NOCASE"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._session() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def list_artists(self, search: str = "") -> list[dict[str, Any]]:
        sql = """
            SELECT artist, COUNT(*) AS track_count,
                   COUNT(DISTINCT album) AS album_count
            FROM tracks
            WHERE artist <> ''
        """
        params: list[Any] = []
        if search.strip():
            sql += " AND artist COLLATE NOCASE LIKE ? ESCAPE '\\'"
            params.append(self._contains(search.strip()))
        sql += " GROUP BY artist ORDER BY lower(artist) COLLATE NOCASE"
        with self._session() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def list_tracks(
        self,
        search: str = "",
        artist: str | None = None,
        album: str | None = None,
        playlist_id: int | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        if playlist_id is not None:
            sql = """
                SELECT t.*, pt.position AS playlist_position
                FROM tracks AS t
                JOIN playlist_tracks AS pt ON pt.track_id = t.id
                WHERE pt.playlist_id = ?
            """
            params.append(int(playlist_id))
            order_by = "pt.position, lower(t.title) COLLATE NOCASE"
        else:
            sql = "SELECT t.* FROM tracks AS t WHERE 1 = 1"
            order_by = "lower(t.album) COLLATE NOCASE, t.track_number, lower(t.title) COLLATE NOCASE"

        if search.strip():
            needle = self._contains(search.strip())
            sql += " AND (t.title COLLATE NOCASE LIKE ? ESCAPE '\\' "
            sql += "OR t.artist COLLATE NOCASE LIKE ? ESCAPE '\\' "
            sql += "OR t.album COLLATE NOCASE LIKE ? ESCAPE '\\')"
            params.extend([needle, needle, needle])
        if artist is not None:
            sql += " AND t.artist = ?"
            params.append(artist)
        if album is not None:
            sql += " AND t.album = ?"
            params.append(album)

        sql += f" ORDER BY {order_by}"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([int(limit), int(offset)])
        with self._session() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def create_playlist(self, name: str) -> int:
        clean_name = " ".join(name.split()).strip() or "Nueva playlist"
        with self._session() as conn:
            try:
                cur = conn.execute("INSERT INTO playlists(name) VALUES(?)", (clean_name,))
                return int(cur.lastrowid)
            except sqlite3.IntegrityError:
                row = conn.execute("SELECT id FROM playlists WHERE name = ?", (clean_name,)).fetchone()
                return int(row[0])

    def rename_playlist(self, playlist_id: int, name: str) -> None:
        clean_name = " ".join(name.split()).strip()
        if not clean_name:
            return
        with self._session() as conn:
            conn.execute("UPDATE playlists SET name = ? WHERE id = ?", (clean_name, playlist_id))

    def delete_playlist(self, playlist_id: int) -> None:
        with self._session() as conn:
            conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))

    def list_playlists(self) -> list[dict[str, Any]]:
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT p.id, p.name, COUNT(pt.track_id) AS track_count
                FROM playlists AS p
                LEFT JOIN playlist_tracks AS pt ON pt.playlist_id = p.id
                GROUP BY p.id
                ORDER BY lower(p.name) COLLATE NOCASE
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def add_to_playlist(self, playlist_id: int, track_id: int) -> None:
        with self._session() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()
            position = int(row[0])
            conn.execute(
                "INSERT OR IGNORE INTO playlist_tracks(playlist_id, track_id, position) VALUES(?, ?, ?)",
                (playlist_id, track_id, position),
            )

    def remove_from_playlist(self, playlist_id: int, track_id: int) -> None:
        with self._session() as conn:
            conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
                (playlist_id, track_id),
            )

    def playlist_name(self, playlist_id: int) -> str | None:
        with self._session() as conn:
            row = conn.execute("SELECT name FROM playlists WHERE id = ?", (playlist_id,)).fetchone()
        return str(row[0]) if row else None
