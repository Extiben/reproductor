"""Optional online artwork lookup.

The player remains local: this module enriches local tracks with metadata and
artwork and can show online search results with authorized downloads; it
never streams music.  iTunes Search API is used for library enrichment, while
Internet Archive is used for downloadable Creative Commons/public-domain
records.  Network work runs in Qt workers so the UI and audio thread stay
responsive.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from .database import LibraryDB
from .metadata import cache_cover


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
ARCHIVE_SEARCH_URL = "https://archive.org/advancedsearch.php"
ARCHIVE_METADATA_URL = "https://archive.org/metadata/{identifier}"
ARCHIVE_DOWNLOAD_URL = "https://archive.org/download/{identifier}/{filename}"
_USER_AGENT = "LocalTune/0.1 (local music artwork lookup)"
_SIZE_RE = re.compile(r"(?P<size>\d+)x(?P<size2>\d+)(?P<suffix>bb)?")
_AUDIO_EXTENSIONS = {".mp3", ".flac", ".ogg", ".oga"}
_LICENSE_MARKERS = ("creativecommons.org", "publicdomain")


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join("".join(char if char.isalnum() else " " for char in without_marks.casefold()).split())


def _similarity(left: str, right: str) -> float:
    left_folded, right_folded = _fold(left), _fold(right)
    if not left_folded or not right_folded:
        return 0.0
    if left_folded == right_folded:
        return 1.0
    ratio = SequenceMatcher(None, left_folded, right_folded).ratio()
    left_tokens, right_tokens = set(left_folded.split()), set(right_folded.split())
    token_ratio = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    return max(ratio, token_ratio)


def _larger_artwork_url(url: str) -> str:
    # iTunes commonly returns .../100x100bb.jpg.  Asking for 320 keeps the
    # on-disk cache small while looking good in a 142px card.
    match = _SIZE_RE.search(url)
    if not match:
        return url
    size = match.group("size")
    return url[: match.start()] + f"320x320{match.group('suffix') or ''}" + url[match.end() :]


def _find_album_result(artist: str, album: str, country: str = "CO") -> dict[str, Any] | None:
    query = urllib.parse.urlencode(
        {
            "term": f"{artist} {album}".strip(),
            "entity": "album",
            "attribute": "albumTerm",
            "limit": "8",
            "country": country,
        }
    )
    request = urllib.request.Request(
        f"{ITUNES_SEARCH_URL}?{query}",
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))

    best: tuple[float, dict[str, Any]] | None = None
    for result in payload.get("results", []):
        result_artist = str(result.get("artistName") or "")
        result_album = str(result.get("collectionName") or "")
        artwork = str(result.get("artworkUrl100") or result.get("artworkUrl60") or "")
        if not artwork:
            continue
        score = 0.55 * _similarity(artist, result_artist) + 0.45 * _similarity(album, result_album)
        if best is None or score > best[0]:
            best = (score, result)

    # Refuse weak matches so a generic album title does not receive the wrong
    # cover.  Users can still keep the local placeholder or rescan later.
    # A stronger threshold is deliberate because the match may also enrich
    # artist/album labels in the local index, not only provide an image.
    return best[1] if best is not None and best[0] >= 0.68 else None


def _get_json(url: str, params: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    full_url = url
    if params:
        full_url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        full_url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    return payload if isinstance(payload, dict) else {}


def _creator_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    return str(value or "")


def _allowed_license(value: Any) -> bool:
    license_url = str(value or "").casefold()
    return any(marker in license_url for marker in _LICENSE_MARKERS)


def _archive_audio_file(identifier: str, files: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for file_info in files:
        name = str(file_info.get("name") or "")
        suffix = Path(name).suffix.casefold()
        if suffix not in _AUDIO_EXTENSIONS:
            continue
        if file_info.get("private") is True or file_info.get("private") == "1":
            continue
        try:
            size = int(file_info.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        # Avoid accidentally offering a multi-gigabyte archive item.  The
        # result can still be viewed online; downloads remain manageable.
        if size and size > 350 * 1024 * 1024:
            continue
        candidates.append({"name": name, "size": size, "format": str(file_info.get("format") or "")})
    if not candidates:
        return None
    # Prefer an MP3/OGG file and then the smallest available audio file.
    candidates.sort(key=lambda item: (0 if Path(item["name"]).suffix.casefold() in {".mp3", ".ogg"} else 1, item["size"] or 10**18))
    chosen = candidates[0]
    chosen["url"] = ARCHIVE_DOWNLOAD_URL.format(
        identifier=urllib.parse.quote(identifier, safe=""),
        filename=urllib.parse.quote(chosen["name"], safe=""),
    )
    return chosen


def search_online_songs(query_text: str, cover_dir: Path, country: str = "CO") -> list[dict[str, Any]]:
    """Search legal audio items with a direct, authorized download file.

    Internet Archive is used here instead of a streaming catalog: results are
    limited to records whose metadata exposes a Creative Commons or public
    domain license.  Availability still depends on the item's rights holder.
    """
    del country  # kept in the function signature for the worker API
    clean_query = " ".join(query_text.replace(":", " ").replace('"', " ").split())
    if not clean_query:
        return []
    archive_query = (
        f"({clean_query}) AND mediatype:audio "
        "AND licenseurl:(*creativecommons.org* OR *publicdomain*)"
    )
    params = [
        ("q", archive_query),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "creator"),
        ("fl[]", "licenseurl"),
        ("rows", "10"),
        ("page", "1"),
        ("output", "json"),
    ]
    payload = _get_json(ARCHIVE_SEARCH_URL, params)
    docs = payload.get("response", {}).get("docs", [])
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        identifier = str(doc.get("identifier") or "")
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        try:
            item = _get_json(ARCHIVE_METADATA_URL.format(identifier=urllib.parse.quote(identifier, safe="")))
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        license_url = str(doc.get("licenseurl") or metadata.get("licenseurl") or "")
        if not _allowed_license(license_url):
            continue
        audio_file = _archive_audio_file(identifier, item.get("files") or [])
        if not audio_file:
            continue

        cover_path: str | None = None
        try:
            artwork_request = urllib.request.Request(
                f"https://archive.org/services/img/{urllib.parse.quote(identifier, safe='')}",
                headers={"User-Agent": _USER_AGENT, "Accept": "image/*"},
            )
            with urllib.request.urlopen(artwork_request, timeout=8) as artwork_response:
                cover_path = cache_cover(artwork_response.read(), cover_dir)
        except (OSError, ValueError, urllib.error.URLError):
            pass

        title = str(metadata.get("title") or doc.get("title") or identifier)
        creator = _creator_text(metadata.get("creator") or doc.get("creator"))
        results.append(
            {
                "online_id": identifier,
                "title": title,
                "artist": creator or "Autor desconocido",
                "album": title,
                "cover_path": cover_path,
                "source_url": f"https://archive.org/details/{urllib.parse.quote(identifier, safe='')}",
                "download_url": audio_file["url"],
                "download_name": audio_file["name"],
                "download_size": audio_file["size"],
                "download_format": audio_file["format"],
                "license_url": license_url,
                "source_name": "Internet Archive",
            }
        )
        if len(results) >= 8:
            break
    return results


class OnlineSearchWorker(QObject):
    finished = Signal(str, object)  # original query, result rows
    failed = Signal(str, str)  # original query, message

    def __init__(self, query: str, cover_dir: str, country: str | None = None):
        super().__init__()
        self.query = query
        self.cover_dir = Path(cover_dir)
        self.country = country or os.environ.get("LOCALTUNE_ITUNES_COUNTRY", "CO")
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        if self._cancel_requested:
            self.finished.emit(self.query, [])
            return
        try:
            results = search_online_songs(self.query, self.cover_dir, self.country)
            self.finished.emit(self.query, results)
        except Exception as exc:
            self.failed.emit(self.query, f"{type(exc).__name__}: {exc}")


class DownloadWorker(QObject):
    progress = Signal(int, int)  # bytes received, total bytes (0 if unknown)
    finished = Signal(str)
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, url: str, destination: str):
        super().__init__()
        self.url = url
        self.destination = Path(destination)
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        temporary = self.destination.with_name(self.destination.name + ".part")
        try:
            if not self.url.startswith("https://archive.org/download/"):
                raise ValueError("La descarga no procede de una URL permitida")
            self.destination.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(
                self.url,
                headers={"User-Agent": _USER_AGENT, "Accept": "audio/*"},
            )
            with urllib.request.urlopen(request, timeout=12) as response:
                try:
                    total = int(response.headers.get("Content-Length") or 0)
                except (TypeError, ValueError):
                    total = 0
                received = 0
                with temporary.open("wb") as output:
                    while True:
                        if self._cancel_requested:
                            output.close()
                            temporary.unlink(missing_ok=True)
                            self.cancelled.emit()
                            return
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        received += len(chunk)
                        self.progress.emit(received, total)
            os.replace(temporary, self.destination)
            self.finished.emit(str(self.destination))
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class CoverLookupWorker(QObject):
    progress = Signal(int, int, str)  # processed groups, total groups, album
    finished = Signal(int, int)  # covers found, groups processed
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, db_path: str, cover_dir: str, country: str | None = None):
        super().__init__()
        self.db_path = db_path
        self.cover_dir = Path(cover_dir)
        self.country = country or os.environ.get("LOCALTUNE_ITUNES_COUNTRY", "CO")
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        try:
            db = LibraryDB(self.db_path)
            db.initialize()
            candidates = db.tracks_for_online_lookup(limit=500)
            groups_by_key: dict[tuple[str, str], list[Any]] = {}
            for row in candidates:
                artist = str(row.get("artist") or "").strip()
                album = str(row.get("album") or "").strip()
                key = (_fold(artist), _fold(album))
                if not artist or not album:
                    continue
                if key not in groups_by_key:
                    groups_by_key[key] = [artist, album, str(row.get("title") or ""), not bool(row.get("cover_path"))]
                else:
                    # One missing image makes the whole album worth looking
                    # up, while metadata can still be checked for all groups.
                    groups_by_key[key][3] = groups_by_key[key][3] or not bool(row.get("cover_path"))
            groups: list[tuple[str, str, str, bool]] = [tuple(value) for value in groups_by_key.values()]

            total = len(groups)
            found = 0
            for number, (artist, album, _title, needs_cover) in enumerate(groups, start=1):
                if self._cancel_requested:
                    self.cancelled.emit()
                    return
                try:
                    result = _find_album_result(artist, album, self.country)
                    if result:
                        cover_path: str | None = None
                        artwork_url = _larger_artwork_url(
                            str(result.get("artworkUrl100") or result.get("artworkUrl60") or "")
                        )
                        if artwork_url and needs_cover:
                            try:
                                request = urllib.request.Request(
                                    artwork_url,
                                    headers={"User-Agent": _USER_AGENT, "Accept": "image/*"},
                                )
                                with urllib.request.urlopen(request, timeout=8) as response:
                                    cover_bytes = response.read()
                                cover_path = cache_cover(cover_bytes, self.cover_dir)
                            except (OSError, ValueError, urllib.error.URLError):
                                # Metadata can still be useful if only the
                                # artwork CDN request failed.
                                cover_path = None
                        found += db.apply_online_album_match(
                            artist=artist,
                            album=album,
                            remote_artist=str(result.get("artistName") or ""),
                            remote_album=str(result.get("collectionName") or ""),
                            cover_path=cover_path,
                        )
                except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError):
                    # One unavailable album must not abort the whole lookup.
                    pass
                self.progress.emit(number, total, album)
                # Keep requests polite without making the common small library
                # case feel slow.  The lookup is explicitly user-triggered.
                if number < total:
                    time.sleep(0.12)

            self.finished.emit(found, total)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
