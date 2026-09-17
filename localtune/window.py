"""Main window and application wiring."""

from __future__ import annotations

import json
import os
from typing import Any

from PySide6.QtCore import QModelIndex, QSize, QThread, QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListView,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .config import APP_NAME, COVERS_DIR, DB_PATH, ensure_data_dirs
from .database import LibraryDB
from .models import AlbumListModel, ArtistTableModel, OnlineResultModel, TrackTableModel
from .online import CoverLookupWorker, DownloadWorker, OnlineSearchWorker
from .player import PlaybackController
from .scanner import ScannerWorker
from .widgets import APP_STYLE, AlbumCardDelegate, CoverCache, EmptyState, PlayerBar, Sidebar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_data_dirs()
        self.db = LibraryDB(DB_PATH)
        self.db.initialize()
        self.cover_cache = CoverCache(max_items=128)
        self.controller = PlaybackController(self)
        self._scan_thread: QThread | None = None
        self._scan_worker: ScannerWorker | None = None
        self._online_thread: QThread | None = None
        self._online_worker: CoverLookupWorker | None = None
        self._online_search_thread: QThread | None = None
        self._online_search_worker: OnlineSearchWorker | None = None
        self._online_search_query = ""
        self._download_thread: QThread | None = None
        self._download_worker: DownloadWorker | None = None
        self._current_playlist_id: int | None = None

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(960, 600)
        self.resize(1240, 780)
        self.setStyleSheet(APP_STYLE)
        self._create_models()
        self._build_ui()
        self.sidebar.set_active("home")
        self._connect_signals()
        self._refresh_everything()
        self._start_saved_scan()

    def _create_models(self) -> None:
        self.home_album_model = AlbumListModel(self.db, self)
        self.library_album_model = AlbumListModel(self.db, self)
        self.search_album_model = AlbumListModel(self.db, self)
        self.artist_model = ArtistTableModel(self.db, self)
        self.library_track_model = TrackTableModel(self.db, self)
        self.search_track_model = TrackTableModel(self.db, self)
        self.online_result_model = OnlineResultModel(self)
        self.playlist_track_model = TrackTableModel(self.db, self)
        self.queue_model = TrackTableModel(self.db, self)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.sidebar = Sidebar()
        body_layout.addWidget(self.sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(22, 16, 22, 0)
        content_layout.setSpacing(10)

        topbar = QHBoxLayout()
        topbar.setSpacing(10)
        self.search_input = self._make_search_input()
        topbar.addWidget(self.search_input, 1)
        self.search_button = QPushButton("Buscar")
        self.search_button.setObjectName("quietButton")
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        topbar.addWidget(self.search_button)
        self.online_button = QPushButton("✦  Carátulas online")
        self.online_button.setObjectName("quietButton")
        self.online_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.online_button.setToolTip("Buscar carátulas y metadatos en Internet, sin descargar audio")
        topbar.addWidget(self.online_button)
        self.scan_button = QPushButton("⟳  Escanear")
        self.scan_button.setObjectName("quietButton")
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.setToolTip("Escanear las carpetas de música guardadas")
        topbar.addWidget(self.scan_button)
        content_layout.addLayout(topbar)

        self.stack = QStackedWidget()
        self._build_home_page()
        self._build_library_page()
        self._build_search_page()
        self._build_playlist_page()
        self._build_queue_page()
        content_layout.addWidget(self.stack, 1)
        body_layout.addWidget(content, 1)
        root_layout.addWidget(body, 1)

        self.player_bar = PlayerBar(self.controller, self.cover_cache)
        root_layout.addWidget(self.player_bar)
        self.setCentralWidget(root)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().setStyleSheet("QStatusBar { background: #181818; color: #a7a7a7; border: none; }")

    @staticmethod
    def _make_search_input() -> "QLineEdit":
        from PySide6.QtWidgets import QLineEdit

        search = QLineEdit()
        search.setPlaceholderText("⌕   Buscar canciones, artistas o álbumes")
        search.setClearButtonEnabled(True)
        search.setMinimumHeight(36)
        return search

    def _build_home_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 12, 2, 8)
        layout.setSpacing(8)

        title = QLabel("Tu música, en local.")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.home_stats = QLabel("Añade una carpeta para comenzar")
        self.home_stats.setObjectName("muted")
        layout.addWidget(self.home_stats)
        layout.addSpacing(18)

        section = QLabel("Álbumes de tu biblioteca")
        section.setObjectName("sectionTitle")
        layout.addWidget(section)
        self.home_empty = EmptyState(
            "Tu biblioteca está vacía",
            "Pulsa «Añadir carpeta de música» para escanear MP3, FLAC y OGG de tu PC.",
        )
        layout.addWidget(self.home_empty)
        self.home_album_view = self._make_album_view(self.home_album_model)
        layout.addWidget(self.home_album_view, 1)
        self.stack.addWidget(page)
        self.home_page = page

    def _build_library_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 12, 2, 8)
        layout.setSpacing(8)
        title = QLabel("Tu biblioteca")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.library_tabs = QTabWidget()

        self.library_album_view = self._make_album_view(self.library_album_model)
        self.library_tabs.addTab(self.library_album_view, "Álbumes")

        self.artist_view = self._make_table_view(self.artist_model, artist_table=True)
        self.library_tabs.addTab(self.artist_view, "Artistas")

        self.library_track_view = self._make_table_view(self.library_track_model)
        self.library_tabs.addTab(self.library_track_view, "Canciones")
        layout.addWidget(self.library_tabs, 1)
        self.stack.addWidget(page)
        self.library_page = page

    def _build_search_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 12, 2, 8)
        layout.setSpacing(7)
        title = QLabel("Buscar")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.search_hint = QLabel("Escribe en el buscador para encontrar tu música al instante.")
        self.search_hint.setObjectName("muted")
        layout.addWidget(self.search_hint)

        albums_title = QLabel("Álbumes")
        albums_title.setObjectName("sectionTitle")
        layout.addWidget(albums_title)
        self.search_album_view = self._make_album_view(self.search_album_model)
        self.search_album_view.setMinimumHeight(215)
        self.search_album_view.setMaximumHeight(245)
        layout.addWidget(self.search_album_view)

        tracks_title = QLabel("Canciones")
        tracks_title.setObjectName("sectionTitle")
        layout.addWidget(tracks_title)
        self.search_track_view = self._make_table_view(self.search_track_model)
        layout.addWidget(self.search_track_view, 1)

        online_header_host = QWidget()
        online_header = QHBoxLayout(online_header_host)
        online_header.setContentsMargins(0, 0, 0, 0)
        self.online_results_title = QLabel("Resultados online")
        self.online_results_title.setObjectName("sectionTitle")
        online_header.addWidget(self.online_results_title)
        online_header.addStretch(1)
        self.online_download_button = QPushButton("⬇  Descargar")
        self.online_download_button.setObjectName("quietButton")
        self.online_download_button.setToolTip("Descargar el resultado seleccionado en la carpeta de música")
        self.online_download_button.setEnabled(False)
        online_header.addWidget(self.online_download_button)
        self.online_results_hint = QLabel("Resultados con licencia Creative Commons o dominio público. No se descarga audio automáticamente.")
        self.online_results_hint.setObjectName("muted")
        self.online_result_view = self._make_table_view(self.online_result_model)
        self.online_result_view.setMinimumHeight(105)
        self.online_result_view.setMaximumHeight(185)
        self.online_result_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.online_result_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.online_result_view.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.online_result_view.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.online_result_view.setColumnWidth(0, 52)
        self.online_result_view.setIconSize(QSize(40, 40))
        self.online_result_view.verticalHeader().setDefaultSectionSize(50)
        self.online_results_header = online_header_host
        for widget in (self.online_results_header, self.online_results_hint, self.online_result_view):
            widget.setVisible(False)
            layout.addWidget(widget)
        self.stack.addWidget(page)
        self.search_page = page

    def _build_playlist_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 12, 2, 8)
        layout.setSpacing(8)
        header = QHBoxLayout()
        self.playlist_title = QLabel("Playlist")
        self.playlist_title.setObjectName("pageTitle")
        header.addWidget(self.playlist_title)
        header.addStretch(1)
        self.playlist_play_button = QPushButton("▶  Reproducir")
        self.playlist_play_button.setObjectName("accentButton")
        self.playlist_delete_button = QPushButton("Eliminar")
        self.playlist_delete_button.setObjectName("quietButton")
        header.addWidget(self.playlist_play_button)
        header.addWidget(self.playlist_delete_button)
        layout.addLayout(header)
        self.playlist_info = QLabel("0 canciones")
        self.playlist_info.setObjectName("muted")
        layout.addWidget(self.playlist_info)
        self.playlist_view = self._make_table_view(self.playlist_track_model)
        layout.addWidget(self.playlist_view, 1)
        self.stack.addWidget(page)
        self.playlist_page = page

    def _build_queue_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 12, 2, 8)
        layout.setSpacing(8)
        header = QHBoxLayout()
        title = QLabel("Cola de reproducción")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.clear_queue_button = QPushButton("Limpiar próximos")
        self.clear_queue_button.setObjectName("quietButton")
        header.addWidget(self.clear_queue_button)
        layout.addLayout(header)
        self.queue_info = QLabel("La cola está vacía")
        self.queue_info.setObjectName("muted")
        layout.addWidget(self.queue_info)
        self.queue_view = self._make_table_view(self.queue_model)
        layout.addWidget(self.queue_view, 1)
        self.stack.addWidget(page)
        self.queue_page = page

    def _make_album_view(self, model: AlbumListModel) -> QListView:
        view = QListView()
        view.setModel(model)
        view.setItemDelegate(AlbumCardDelegate(self.cover_cache, view))
        view.setViewMode(QListView.ViewMode.IconMode)
        view.setFlow(QListView.Flow.LeftToRight)
        view.setResizeMode(QListView.ResizeMode.Adjust)
        view.setMovement(QListView.Movement.Static)
        view.setSpacing(7)
        view.setGridSize(QSize(170, 216))
        view.setUniformItemSizes(True)
        view.setBatchSize(60)
        view.setWrapping(True)
        view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.doubleClicked.connect(self._album_activated)
        return view

    def _make_table_view(self, model, artist_table: bool = False) -> QTableView:
        view = QTableView()
        view.setModel(model)
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setShowGrid(False)
        view.setAlternatingRowColors(False)
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.verticalHeader().setVisible(False)
        view.verticalHeader().setDefaultSectionSize(43)
        view.horizontalHeader().setHighlightSections(False)
        view.horizontalHeader().setStretchLastSection(False)
        view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, model.columnCount()):
            view.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        view.customContextMenuRequested.connect(lambda pos, target=view: self._track_context_menu(target, pos))
        if artist_table:
            view.doubleClicked.connect(self._artist_activated)
        else:
            view.doubleClicked.connect(self._track_activated)
        return view

    def _connect_signals(self) -> None:
        self.sidebar.navigate.connect(self._navigate)
        self.sidebar.playlistSelected.connect(self.show_playlist)
        self.sidebar.createPlaylistRequested.connect(self.create_playlist)
        self.sidebar.addFolderRequested.connect(self.add_music_folder)
        self.scan_button.clicked.connect(self.start_scan)
        self.search_button.clicked.connect(self._perform_search)
        self.online_button.clicked.connect(self.start_online_cover_lookup)
        self.online_download_button.clicked.connect(self.download_selected_online)
        self.online_result_view.selectionModel().selectionChanged.connect(
            lambda *_args: self._update_online_download_button()
        )
        self.player_bar.queueRequested.connect(self.show_queue)
        self.playlist_play_button.clicked.connect(self.play_current_playlist)
        self.playlist_delete_button.clicked.connect(self.delete_current_playlist)
        self.clear_queue_button.clicked.connect(self.controller.clear_upcoming)
        self.controller.queueChanged.connect(self._refresh_queue)
        self.controller.errorMessage.connect(lambda message: self.statusBar().showMessage(message, 6000))

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(140)
        self.search_input.textChanged.connect(lambda _text: self.search_timer.start())
        self.search_input.returnPressed.connect(self._perform_search)
        self.search_timer.timeout.connect(self._perform_search)
        self.online_search_timer = QTimer(self)
        self.online_search_timer.setSingleShot(True)
        self.online_search_timer.setInterval(650)
        self.search_input.textChanged.connect(self._schedule_online_search)
        self.online_search_timer.timeout.connect(self._maybe_start_online_search)
        self.library_tabs.currentChanged.connect(self._library_tab_changed)

    def _refresh_everything(self) -> None:
        playlists = self.db.list_playlists()
        self.sidebar.set_playlists(playlists)
        count = self.db.count_tracks()
        self.home_stats.setText(
            f"{count:,} {'canciones' if count != 1 else 'canción'} · biblioteca local".replace(",", ".")
            if count
            else "Añade una carpeta para comenzar"
        )
        # Albums and artists are compact grouped rows.  Cards themselves are
        # painted lazily by AlbumCardDelegate, and song rows fetch in pages.
        self.home_album_model.reload(limit=24)
        self.library_album_model.reload()
        self.artist_model.reload()
        self.library_track_model.reload(limit=250)
        self.home_empty.setVisible(self.home_album_model.rowCount() == 0)
        if self.search_input.text().strip():
            self._perform_search()
        if self._current_playlist_id is not None:
            self.show_playlist(self._current_playlist_id)
        self._refresh_queue()

    def _refresh_queue(self) -> None:
        rows = self.controller.queue_snapshot()
        self.queue_model.set_rows(rows)
        count = len(rows)
        self.queue_info.setText(
            f"{count} {'canciones en cola' if count != 1 else 'canción en cola'}"
            if count
            else "La cola está vacía"
        )

    def _navigate(self, destination: str) -> None:
        if destination == "search":
            self.sidebar.set_active("search")
            self.stack.setCurrentWidget(self.search_page)
            self.search_input.setFocus()
            self._perform_search()
            return
        self.search_input.clear()
        self.sidebar.set_active(destination)
        pages = {
            "home": self.home_page,
            "library": self.library_page,
            "queue": self.queue_page,
        }
        page = pages.get(destination)
        if page is not None:
            self.stack.setCurrentWidget(page)
        if destination == "library":
            self._refresh_library_models()
        elif destination == "queue":
            self._refresh_queue()

    def _refresh_library_models(self) -> None:
        self.library_album_model.reload()
        self.artist_model.reload()
        self.library_track_model.reload(limit=250)

    def _perform_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.online_search_timer.stop()
            self._hide_online_results()
            self.search_hint.setText("Escribe en el buscador para encontrar tu música al instante.")
            self.search_album_model.reload(search="", limit=0)
            self.search_track_model.set_rows([])
            return
        self.sidebar.set_active("search")
        self.stack.setCurrentWidget(self.search_page)
        self.search_hint.setText(f"Resultados locales para «{query}»")
        self.search_album_model.reload(search=query, limit=30)
        self.search_track_model.reload(search=query, limit=250)
        # Also schedule a remote metadata lookup when the local index has no
        # match.  It is intentionally delayed and never downloads audio.
        self._schedule_online_search()

    def _schedule_online_search(self, _text: str | None = None) -> None:
        self.online_search_timer.stop()
        query = self.search_input.text().strip()
        if len(query) < 3:
            self._hide_online_results()
            return
        self.online_search_timer.start()

    def _maybe_start_online_search(self) -> None:
        query = self.search_input.text().strip()
        if len(query) < 3:
            return
        if self.search_album_model.rowCount() or self.search_track_model.rowCount():
            self._hide_online_results()
            return
        if self._online_search_thread is not None and self._online_search_thread.isRunning():
            return

        self.online_results_header.setVisible(True)
        self.online_results_hint.setVisible(True)
        self.online_results_hint.setText("Buscando resultados legales con metadatos, carátula y descarga disponible…")
        self.online_result_view.setVisible(False)
        self.online_download_button.setEnabled(False)
        thread = QThread(self)
        worker = OnlineSearchWorker(query, str(COVERS_DIR))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._online_search_finished)
        worker.failed.connect(self._online_search_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._online_search_thread_finished)
        self._online_search_query = query
        self._online_search_thread = thread
        self._online_search_worker = worker
        thread.start()

    def _hide_online_results(self) -> None:
        self.online_result_model.set_rows([])
        self.online_results_header.setVisible(False)
        self.online_results_hint.setVisible(False)
        self.online_result_view.setVisible(False)
        self.online_download_button.setEnabled(False)

    def _online_search_finished(self, query: str, rows: object) -> None:
        current_query = self.search_input.text().strip()
        if query != current_query:
            self._hide_online_results()
            return
        if self.search_album_model.rowCount() or self.search_track_model.rowCount():
            self._hide_online_results()
            return
        result_rows = rows if isinstance(rows, list) else []
        self.online_result_model.set_rows(result_rows)
        self.online_results_header.setVisible(True)
        self.online_results_hint.setVisible(True)
        self.online_results_hint.setText(
            "Resultados legales de Internet Archive. Selecciona uno para descargarlo en tu carpeta de música."
            if result_rows
            else "No se encontraron coincidencias descargables con licencia abierta."
        )
        self.online_result_view.setVisible(bool(result_rows))
        self._update_online_download_button()

    def _online_search_failed(self, query: str, _message: str) -> None:
        if query == self.search_input.text().strip():
            self._hide_online_results()

    def _update_online_download_button(self) -> None:
        indexes = self.online_result_view.selectionModel().selectedRows()
        row = indexes[0].data(Qt.ItemDataRole.UserRole) if indexes else None
        enabled = bool(isinstance(row, dict) and row.get("download_url"))
        if self._download_thread is not None and self._download_thread.isRunning():
            enabled = False
        self.online_download_button.setEnabled(enabled)

    @staticmethod
    def _safe_download_name(row: dict[str, Any]) -> str:
        original = str(row.get("download_name") or "").strip()
        name = os.path.basename(original)
        if not name or name in {".", ".."}:
            name = f"{row.get('artist', 'Audio')} - {row.get('title', 'Descarga')}.mp3"
        invalid = '<>:"/\\|?*'
        name = "".join("_" if char in invalid or ord(char) < 32 else char for char in name).strip(" .")
        return name or "LocalTune-download.mp3"

    def download_selected_online(self) -> None:
        indexes = self.online_result_view.selectionModel().selectedRows()
        row = indexes[0].data(Qt.ItemDataRole.UserRole) if indexes else None
        if not isinstance(row, dict) or not row.get("download_url"):
            return
        if self._download_thread is not None and self._download_thread.isRunning():
            return

        roots = self._saved_roots()
        if not roots:
            folder = QFileDialog.getExistingDirectory(self, "Elige tu carpeta de música", os.path.expanduser("~"))
            if not folder:
                return
            root = os.path.normpath(os.path.abspath(folder))
            roots = [root]
            self.db.set_setting("music_roots", json.dumps(roots, ensure_ascii=False))
        destination_dir = os.path.join(roots[0], "LocalTune Downloads")
        os.makedirs(destination_dir, exist_ok=True)
        filename = self._safe_download_name(row)
        destination = os.path.join(destination_dir, filename)
        stem, suffix = os.path.splitext(filename)
        counter = 2
        while os.path.exists(destination):
            destination = os.path.join(destination_dir, f"{stem} ({counter}){suffix}")
            counter += 1

        self.online_download_button.setEnabled(False)
        self.online_results_hint.setText("Descargando archivo autorizado…")
        self.statusBar().showMessage(f"Descargando {filename}…")
        thread = QThread(self)
        worker = DownloadWorker(str(row["download_url"]), destination)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._download_progress)
        worker.finished.connect(self._download_finished)
        worker.cancelled.connect(self._download_cancelled)
        worker.failed.connect(self._download_failed)
        worker.finished.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.cancelled.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._download_thread_finished)
        self._download_thread = thread
        self._download_worker = worker
        thread.start()

    @staticmethod
    def _format_bytes(value: int) -> str:
        size = float(max(0, value))
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{value} B"

    def _download_progress(self, received: int, total: int) -> None:
        if total:
            text = f"Descargando {self._format_bytes(received)} / {self._format_bytes(total)}"
        else:
            text = f"Descargando {self._format_bytes(received)}"
        self.statusBar().showMessage(text)

    def _download_finished(self, path: str) -> None:
        self.statusBar().showMessage(f"Descarga completada: {os.path.basename(path)}", 5000)
        self.online_results_hint.setText("Descarga completada. Actualizando la biblioteca local…")
        self.start_scan()

    def _download_cancelled(self) -> None:
        self.statusBar().showMessage("Descarga cancelada", 3000)
        self._update_online_download_button()

    def _download_failed(self, message: str) -> None:
        self.statusBar().showMessage(f"No se pudo descargar: {message}", 7000)
        self.online_results_hint.setText("No se pudo completar la descarga.")
        self._update_online_download_button()

    def _download_thread_finished(self) -> None:
        self._download_thread = None
        self._download_worker = None
        self._update_online_download_button()

    def _online_search_thread_finished(self) -> None:
        finished_query = self._online_search_query
        self._online_search_thread = None
        self._online_search_worker = None
        current_query = self.search_input.text().strip()
        if (
            current_query
            and current_query != finished_query
            and len(current_query) >= 3
            and not self.search_album_model.rowCount()
            and not self.search_track_model.rowCount()
        ):
            self.online_search_timer.start()

    def _library_tab_changed(self, index: int) -> None:
        if index == 2:
            self.library_track_model.reload(limit=250)

    def _album_activated(self, index: QModelIndex) -> None:
        row = index.data(Qt.ItemDataRole.UserRole)
        if not row:
            return
        tracks = self.db.list_tracks(album=str(row.get("album", "")))
        self.controller.play_tracks(tracks, 0)
        self.statusBar().showMessage(f"Reproduciendo {row.get('album', '')}", 3000)

    def _artist_activated(self, index: QModelIndex) -> None:
        row = index.data(Qt.ItemDataRole.UserRole)
        if not row:
            return
        artist = str(row.get("artist", ""))
        self.library_tabs.setCurrentIndex(2)
        self.library_track_model.reload(artist=artist, limit=250)
        self.sidebar.set_active("library")
        self.stack.setCurrentWidget(self.library_page)
        self.statusBar().showMessage(f"Mostrando canciones de {artist}", 3000)

    def _track_activated(self, index: QModelIndex) -> None:
        model = index.model()
        if not isinstance(model, TrackTableModel):
            return
        track = model.track_at(index.row())
        if not track:
            return
        self.controller.play_tracks(model.all_tracks(), index.row())

    def _track_context_menu(self, view: QTableView, position) -> None:
        index = view.indexAt(position)
        if not index.isValid():
            return
        model = view.model()
        if not isinstance(model, TrackTableModel):
            return
        track = model.track_at(index.row())
        if not track:
            return
        menu = QMenu(view)
        play_action = menu.addAction("▶  Reproducir ahora")
        next_action = menu.addAction("Añadir a continuación")
        menu.addSeparator()
        playlist_menu = menu.addMenu("Añadir a playlist")
        playlists = self.db.list_playlists()
        if not playlists:
            empty = playlist_menu.addAction("Crea una playlist primero")
            empty.setEnabled(False)
        else:
            for playlist in playlists:
                action = playlist_menu.addAction(str(playlist["name"]))
                playlist_id = int(playlist["id"])
                track_id = int(track["id"])
                action.triggered.connect(
                    lambda _checked=False, pid=playlist_id, tid=track_id: self._add_to_playlist(pid, tid)
                )
        remove_action = None
        if view is self.playlist_view and self._current_playlist_id is not None:
            menu.addSeparator()
            remove_action = menu.addAction("Quitar de esta playlist")
        chosen = menu.exec(view.viewport().mapToGlobal(position))
        if chosen == play_action:
            self.controller.play_tracks(model.all_tracks(), index.row())
        elif chosen == next_action:
            self.controller.enqueue_next(track)
        elif remove_action is not None and chosen == remove_action:
            self.db.remove_from_playlist(self._current_playlist_id, int(track["id"]))
            self.show_playlist(self._current_playlist_id)

    def _add_to_playlist(self, playlist_id: int, track_id: int) -> None:
        self.db.add_to_playlist(playlist_id, track_id)
        self.sidebar.set_playlists(self.db.list_playlists())
        self.statusBar().showMessage("Añadida a la playlist", 2500)
        if self._current_playlist_id == playlist_id:
            self.show_playlist(playlist_id)

    def create_playlist(self) -> None:
        name, accepted = QInputDialog.getText(self, "Nueva playlist", "Nombre:")
        if not accepted:
            return
        playlist_id = self.db.create_playlist(name)
        self.sidebar.set_playlists(self.db.list_playlists())
        self.show_playlist(playlist_id)

    def show_playlist(self, playlist_id: int) -> None:
        name = self.db.playlist_name(int(playlist_id))
        if name is None:
            return
        self._current_playlist_id = int(playlist_id)
        self.playlist_title.setText(name)
        self.playlist_track_model.reload(playlist_id=self._current_playlist_id)
        count = self.playlist_track_model.rowCount()
        self.playlist_info.setText(f"{count} {'canciones' if count != 1 else 'canción'}")
        self.stack.setCurrentWidget(self.playlist_page)
        self.search_input.clear()

    def play_current_playlist(self) -> None:
        tracks = self.playlist_track_model.all_tracks()
        if tracks:
            self.controller.play_tracks(tracks, 0)

    def delete_current_playlist(self) -> None:
        if self._current_playlist_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Eliminar playlist",
            f"¿Eliminar «{self.playlist_title.text()}»? Las canciones no se borrarán de tu PC.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_playlist(self._current_playlist_id)
        self._current_playlist_id = None
        self.sidebar.set_playlists(self.db.list_playlists())
        self._navigate("home")

    def show_queue(self) -> None:
        self._refresh_queue()
        self.sidebar.set_active("queue")
        self.stack.setCurrentWidget(self.queue_page)

    def add_music_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecciona una carpeta de música", os.path.expanduser("~"))
        if not folder:
            return
        roots = self._saved_roots()
        normalized = os.path.normpath(os.path.abspath(folder))
        if normalized not in roots:
            roots.append(normalized)
            self.db.set_setting("music_roots", json.dumps(roots, ensure_ascii=False))
        self.start_scan()

    def _saved_roots(self) -> list[str]:
        raw = self.db.get_setting("music_roots", "[]")
        try:
            roots = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            roots = []
        if not isinstance(roots, list):
            return []
        return [str(root) for root in roots if isinstance(root, str) and os.path.isdir(root)]

    def _start_saved_scan(self) -> None:
        roots = self._saved_roots()
        if roots:
            # Let the first paint happen before walking the disk.  The scan is
            # still fully asynchronous and does not delay the window startup.
            QTimer.singleShot(80, self.start_scan)

    def start_scan(self) -> None:
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self.statusBar().showMessage("Ya hay un escaneo en curso", 2500)
            return
        roots = self._saved_roots()
        if not roots:
            self.statusBar().showMessage("Añade una carpeta de música para escanear", 4000)
            return

        self.scan_button.setEnabled(False)
        self.sidebar.set_scan_status("Escaneando biblioteca…")
        thread = QThread(self)
        worker = ScannerWorker(roots, str(DB_PATH), str(COVERS_DIR))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._scan_progress)
        worker.finished.connect(self._scan_finished)
        worker.cancelled.connect(self._scan_cancelled)
        worker.failed.connect(self._scan_failed)
        worker.finished.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.cancelled.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._scan_thread_finished)
        self._scan_thread = thread
        self._scan_worker = worker
        thread.start()

    def _scan_progress(self, processed: int, total: int, filename: str) -> None:
        if total:
            text = f"Escaneando {processed}/{total} · {filename}"
        else:
            text = "No se encontraron archivos de audio"
        self.sidebar.set_scan_status(text)
        self.statusBar().showMessage(text)

    def _scan_finished(self, processed: int) -> None:
        self.scan_button.setEnabled(True)
        self.sidebar.set_scan_status("Biblioteca actualizada")
        self.statusBar().showMessage(f"Escaneo terminado · {processed} archivos revisados", 5000)
        self.cover_cache.clear()
        self._refresh_everything()

    def _scan_cancelled(self) -> None:
        self.scan_button.setEnabled(True)
        self.sidebar.set_scan_status("Escaneo cancelado")
        self.statusBar().showMessage("Escaneo cancelado", 3000)

    def _scan_failed(self, message: str) -> None:
        self.scan_button.setEnabled(True)
        self.sidebar.set_scan_status("Error al escanear")
        self.statusBar().showMessage(message, 7000)

    def _scan_thread_finished(self) -> None:
        self._scan_thread = None
        self._scan_worker = None

    def start_online_cover_lookup(self) -> None:
        """Enrich the local index with artwork and metadata, never audio."""
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self.statusBar().showMessage("Espera a que termine el escaneo local", 3500)
            return
        if self._online_thread is not None and self._online_thread.isRunning():
            self.statusBar().showMessage("La búsqueda de carátulas ya está en curso", 3000)
            return
        if self._online_search_thread is not None and self._online_search_thread.isRunning():
            self.statusBar().showMessage("Espera a que termine la búsqueda online", 3000)
            return
        if not self.db.tracks_for_online_lookup(limit=1):
            self.statusBar().showMessage("No hay canciones en la biblioteca para buscar", 3500)
            return

        self.online_button.setEnabled(False)
        self.sidebar.set_scan_status("Buscando carátulas online…")
        thread = QThread(self)
        worker = CoverLookupWorker(str(DB_PATH), str(COVERS_DIR))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._online_cover_progress)
        worker.finished.connect(self._online_cover_finished)
        worker.cancelled.connect(self._online_cover_cancelled)
        worker.failed.connect(self._online_cover_failed)
        worker.finished.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.cancelled.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._online_thread_finished)
        self._online_thread = thread
        self._online_worker = worker
        thread.start()

    def _online_cover_progress(self, processed: int, total: int, album: str) -> None:
        text = f"Buscando carátulas {processed}/{total} · {album}"
        self.sidebar.set_scan_status(text)
        self.statusBar().showMessage(text)

    def _online_cover_finished(self, found: int, groups: int) -> None:
        self.online_button.setEnabled(True)
        self.sidebar.set_scan_status("Carátulas actualizadas")
        self.statusBar().showMessage(
            f"Búsqueda online terminada · {found} pistas actualizadas en {groups} álbumes",
            6000,
        )
        self.cover_cache.clear()
        self._refresh_everything()

    def _online_cover_cancelled(self) -> None:
        self.online_button.setEnabled(True)
        self.sidebar.set_scan_status("Búsqueda de carátulas cancelada")
        self.statusBar().showMessage("Búsqueda de carátulas cancelada", 3000)

    def _online_cover_failed(self, message: str) -> None:
        self.online_button.setEnabled(True)
        self.sidebar.set_scan_status("Error al buscar carátulas")
        self.statusBar().showMessage(message, 7000)

    def _online_thread_finished(self) -> None:
        self._online_thread = None
        self._online_worker = None

    def closeEvent(self, event) -> None:
        if self._scan_worker is not None:
            self._scan_worker.request_cancel()
        if self._online_worker is not None:
            self._online_worker.request_cancel()
        if self._online_search_worker is not None:
            self._online_search_worker.request_cancel()
        if self._download_worker is not None:
            self._download_worker.request_cancel()
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self._scan_thread.quit()
            self._scan_thread.wait(2500)
        if self._online_thread is not None and self._online_thread.isRunning():
            self._online_thread.quit()
            self._online_thread.wait(9000)
        if self._online_search_thread is not None and self._online_search_thread.isRunning():
            self._online_search_thread.quit()
            self._online_search_thread.wait(9000)
        if self._download_thread is not None and self._download_thread.isRunning():
            self._download_thread.quit()
            self._download_thread.wait(14000)
        event.accept()
