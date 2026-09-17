"""Reusable low-overhead Qt widgets for the LocalTune interface."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QStyle,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .models import format_duration


APP_STYLE = """
QWidget {
    background: #121212;
    color: #f5f5f5;
    font-family: "Segoe UI", "Noto Sans", Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background: #121212;
}
QFrame#sidebar {
    background: #181818;
    border: none;
}
QFrame#playerBar {
    background: #181818;
    border-top: 1px solid #2a2a2a;
}
QLabel#brand {
    color: #ffffff;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#pageTitle {
    color: #ffffff;
    font-size: 28px;
    font-weight: 700;
}
QLabel#sectionTitle {
    color: #ffffff;
    font-size: 19px;
    font-weight: 700;
}
QLabel#muted {
    color: #a7a7a7;
}
QToolButton#navButton, QToolButton#playlistButton {
    border: none;
    border-radius: 6px;
    color: #b3b3b3;
    text-align: left;
    padding: 10px 12px;
    font-size: 14px;
}
QToolButton#navButton:hover, QToolButton#playlistButton:hover {
    color: #ffffff;
    background: #242424;
}
QToolButton#navButton:checked {
    color: #ffffff;
    background: #2a2a2a;
    font-weight: 700;
}
QToolButton#playlistButton {
    padding: 7px 8px;
    font-size: 13px;
}
QToolButton#smallButton, QToolButton#transportButton {
    border: none;
    border-radius: 18px;
    color: #d0d0d0;
    background: transparent;
    padding: 5px;
    font-size: 16px;
}
QToolButton#smallButton:hover, QToolButton#transportButton:hover {
    color: #ffffff;
    background: #2a2a2a;
}
QToolButton#transportButton[playButton="true"] {
    color: #121212;
    background: #ffffff;
    font-size: 17px;
    font-weight: 700;
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}
QToolButton#transportButton[playButton="true"]:hover {
    background: #1DB954;
}
QToolButton#transportButton[active="true"] {
    color: #1DB954;
}
QPushButton#accentButton {
    background: #1DB954;
    color: #071b0d;
    border: none;
    border-radius: 16px;
    padding: 8px 15px;
    font-weight: 700;
}
QPushButton#accentButton:hover {
    background: #1ed760;
}
QPushButton#quietButton {
    color: #d0d0d0;
    background: #242424;
    border: 1px solid #333333;
    border-radius: 14px;
    padding: 7px 13px;
}
QPushButton#quietButton:hover {
    background: #303030;
    color: #ffffff;
}
QLineEdit {
    background: #2a2a2a;
    color: #ffffff;
    border: 1px solid transparent;
    border-radius: 18px;
    padding: 8px 14px;
    selection-background-color: #1DB954;
}
QLineEdit:focus {
    border: 1px solid #5f5f5f;
}
QListView, QTableView {
    background: #121212;
    border: none;
    outline: none;
    alternate-background-color: #171717;
}
QTableView {
    gridline-color: transparent;
    selection-background-color: #2a2a2a;
    selection-color: #ffffff;
}
QTableView::item {
    border-bottom: 1px solid #202020;
    padding: 5px;
}
QTableView::item:hover {
    background: #222222;
}
QHeaderView::section {
    background: #181818;
    color: #a7a7a7;
    border: none;
    border-bottom: 1px solid #2d2d2d;
    padding: 8px;
    font-weight: 600;
}
QTabWidget::pane {
    border: none;
}
QTabBar::tab {
    color: #a7a7a7;
    background: transparent;
    border: none;
    padding: 10px 14px;
    margin-right: 3px;
}
QTabBar::tab:selected {
    color: #ffffff;
    border-bottom: 2px solid #1DB954;
}
QTabBar::tab:hover {
    color: #ffffff;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #4d4d4d;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
    background: #ffffff;
}
QSlider::sub-page:horizontal {
    background: #1DB954;
    border-radius: 2px;
}
QScrollBar:vertical {
    width: 9px;
    background: transparent;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #4b4b4b;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #686868;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0px;
    background: transparent;
}
QMenu {
    background: #242424;
    color: #ffffff;
    border: 1px solid #3a3a3a;
    padding: 5px;
}
QMenu::item {
    padding: 7px 25px 7px 12px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #333333;
}
QProgressBar {
    border: none;
    background: #2a2a2a;
    border-radius: 3px;
    height: 6px;
}
QProgressBar::chunk {
    background: #1DB954;
    border-radius: 3px;
}
"""


def placeholder_pixmap(size: int = 64) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillRect(pixmap.rect(), Qt.GlobalColor.transparent)
    painter.setBrush(Qt.GlobalColor.transparent)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.fillRect(pixmap.rect(), QtGuiColor("#282828"))
    painter.setPen(QtGuiColor("#6f6f6f"))
    font = QFont("Segoe UI Symbol", max(14, int(size * 0.40)))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "♪")
    painter.end()
    return pixmap


def QtGuiColor(value: str):
    # Kept as a function to avoid exposing QColor in every widget import.
    from PySide6.QtGui import QColor

    return QColor(value)


class CoverCache:
    """Small LRU of already-scaled pixmaps; source thumbnails live on disk."""

    def __init__(self, max_items: int = 128):
        self.max_items = max(16, max_items)
        self._items: OrderedDict[tuple[str, int], QPixmap] = OrderedDict()

    def clear(self) -> None:
        self._items.clear()

    def pixmap(self, path: str | None, size: int) -> QPixmap:
        normalized = str(path or "")
        key = (normalized, int(size))
        cached = self._items.get(key)
        if cached is not None:
            self._items.move_to_end(key)
            return cached

        pixmap = QPixmap()
        if normalized and Path(normalized).is_file():
            pixmap.load(normalized)
        if pixmap.isNull():
            pixmap = placeholder_pixmap(size)
        else:
            pixmap = pixmap.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._items[key] = pixmap
        self._items.move_to_end(key)
        while len(self._items) > self.max_items:
            self._items.popitem(last=False)
        return pixmap


class AlbumCardDelegate(QStyledItemDelegate):
    """Paints album cards directly; no QWidget is created per album."""

    def __init__(self, cache: CoverCache, parent=None):
        super().__init__(parent)
        self.cache = cache

    def sizeHint(self, option, index) -> QSize:
        return QSize(170, 216)

    def paint(self, painter: QPainter, option, index) -> None:
        row = index.data(Qt.ItemDataRole.UserRole) or {}
        body = option.rect.adjusted(4, 5, -4, -5)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if option.state & QStyle.StateFlag.State_Selected:
            background = QtGuiColor("#2c2c2c")
        elif option.state & QStyle.StateFlag.State_MouseOver:
            background = QtGuiColor("#202020")
        else:
            background = QtGuiColor("#181818")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(body, 9, 9)

        side = max(36, min(body.width() - 20, 142))
        cover_rect = body.adjusted((body.width() - side) // 2, 10, 0, 0)
        cover_rect.setSize(QSize(side, side))
        clip = QPainterPath()
        clip.addRoundedRect(cover_rect, 7, 7)
        painter.save()
        painter.setClipPath(clip)
        cover = self.cache.pixmap(row.get("cover_path"), side)
        painter.drawPixmap(cover_rect, cover)
        painter.restore()

        title = str(row.get("album", "Álbum desconocido"))
        artist = str(row.get("artist", "Artista desconocido"))
        metrics = QFontMetrics(painter.font())
        title_rect = body.adjusted(10, side + 19, -10, 0)
        painter.setPen(QtGuiColor("#ffffff"))
        title_font = QFont(painter.font())
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, metrics.elidedText(title, Qt.TextElideMode.ElideRight, title_rect.width()))
        normal_font = QFont(painter.font())
        normal_font.setWeight(QFont.Weight.Normal)
        painter.setFont(normal_font)
        painter.setPen(QtGuiColor("#a7a7a7"))
        artist_rect = body.adjusted(10, side + 41, -10, -7)
        subtitle = artist
        count = row.get("track_count")
        if count:
            subtitle = f"{artist} · {count} pistas"
        painter.drawText(artist_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, metrics.elidedText(subtitle, Qt.TextElideMode.ElideRight, artist_rect.width()))
        painter.restore()


class Sidebar(QFrame):
    navigate = Signal(str)
    playlistSelected = Signal(int)
    createPlaylistRequested = Signal()
    addFolderRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(226)
        self._nav_buttons: dict[str, QToolButton] = {}
        self._playlist_layout: QVBoxLayout | None = None
        self._playlist_empty: QLabel | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 14, 14)
        layout.setSpacing(7)

        brand = QLabel("♪  LOCALTUNE")
        brand.setObjectName("brand")
        brand.setMinimumHeight(34)
        layout.addWidget(brand)
        layout.addSpacing(9)

        for key, label in (
            ("home", "⌂   Inicio"),
            ("search", "⌕   Buscar"),
            ("library", "▦   Tu biblioteca"),
            ("queue", "≡   Cola de reproducción"),
        ):
            button = self._make_nav_button(label, key)
            layout.addWidget(button)

        layout.addSpacing(20)
        playlist_header = QHBoxLayout()
        playlist_header.setContentsMargins(8, 0, 0, 0)
        playlist_label = QLabel("TUS PLAYLISTS")
        playlist_label.setObjectName("muted")
        playlist_label.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        playlist_header.addWidget(playlist_label)
        playlist_header.addStretch(1)
        add_button = QToolButton()
        add_button.setObjectName("smallButton")
        add_button.setText("+")
        add_button.setToolTip("Crear playlist")
        add_button.clicked.connect(lambda _checked=False: self.createPlaylistRequested.emit())
        playlist_header.addWidget(add_button)
        layout.addLayout(playlist_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        playlist_host = QWidget()
        self._playlist_layout = QVBoxLayout(playlist_host)
        self._playlist_layout.setContentsMargins(0, 7, 0, 0)
        self._playlist_layout.setSpacing(2)
        self._playlist_empty = QLabel("Aún no tienes playlists")
        self._playlist_empty.setObjectName("muted")
        self._playlist_empty.setWordWrap(True)
        self._playlist_empty.setContentsMargins(8, 5, 5, 5)
        self._playlist_layout.addWidget(self._playlist_empty)
        self._playlist_layout.addStretch(1)
        scroll.setWidget(playlist_host)
        layout.addWidget(scroll, 1)

        folder_button = QPushButton("＋  Añadir carpeta de música")
        folder_button.setObjectName("quietButton")
        folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        folder_button.clicked.connect(lambda _checked=False: self.addFolderRequested.emit())
        layout.addWidget(folder_button)
        self.status_label = QLabel("Biblioteca lista")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        self.status_label.setContentsMargins(8, 3, 8, 0)
        layout.addWidget(self.status_label)

    def _make_nav_button(self, label: str, key: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName("navButton")
        button.setText(label)
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, value=key: self.navigate.emit(value))
        self._nav_buttons[key] = button
        return button

    def set_active(self, key: str) -> None:
        if key in self._nav_buttons:
            self._nav_buttons[key].setChecked(True)

    def set_scan_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_playlists(self, playlists: list[dict[str, Any]]) -> None:
        if self._playlist_layout is None:
            return
        # Remove all dynamic buttons and the empty label, preserving stretch.
        while self._playlist_layout.count():
            item = self._playlist_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not playlists:
            empty = QLabel("Aún no tienes playlists")
            empty.setObjectName("muted")
            empty.setWordWrap(True)
            empty.setContentsMargins(8, 5, 5, 5)
            self._playlist_layout.addWidget(empty)
        else:
            for playlist in playlists:
                button = QToolButton()
                button.setObjectName("playlistButton")
                button.setText(f"♫  {playlist['name']}")
                button.setToolTip(f"{playlist['track_count']} pistas")
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                playlist_id = int(playlist["id"])
                button.clicked.connect(lambda _checked=False, value=playlist_id: self.playlistSelected.emit(value))
                self._playlist_layout.addWidget(button)
        self._playlist_layout.addStretch(1)


class PlayerBar(QFrame):
    queueRequested = Signal()

    def __init__(self, controller, cover_cache: CoverCache, parent=None):
        super().__init__(parent)
        self.setObjectName("playerBar")
        self.setFixedHeight(92)
        self.controller = controller
        self.cover_cache = cover_cache
        self._current_path = ""

        root = QHBoxLayout(self)
        root.setContentsMargins(18, 10, 18, 10)
        root.setSpacing(16)

        left = QWidget()
        left.setMinimumWidth(220)
        left.setMaximumWidth(300)
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        self.cover = QLabel()
        self.cover.setFixedSize(56, 56)
        self.cover.setPixmap(placeholder_pixmap(56))
        left_layout.addWidget(self.cover)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = QLabel("Nada reproduciéndose")
        self.title.setStyleSheet("font-weight: 700; color: #ffffff;")
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.artist = QLabel("Elige una canción de tu biblioteca")
        self.artist.setObjectName("muted")
        self.artist.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        text.addStretch(1)
        text.addWidget(self.title)
        text.addWidget(self.artist)
        text.addStretch(1)
        left_layout.addLayout(text, 1)
        root.addWidget(left, 1)

        center = QVBoxLayout()
        center.setSpacing(4)
        controls = QHBoxLayout()
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls.setSpacing(9)
        self.shuffle_button = self._transport("⤨", "Aleatorio")
        self.previous_button = self._transport("|◀", "Anterior")
        self.play_button = self._transport("▶", "Reproducir / pausar")
        self.play_button.setProperty("playButton", "true")
        self.next_button = self._transport("▶|", "Siguiente")
        self.repeat_button = self._transport("↻", "Repetir: desactivado")
        controls.addWidget(self.shuffle_button)
        controls.addWidget(self.previous_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.repeat_button)
        center.addLayout(controls)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(7)
        self.elapsed = QLabel("0:00")
        self.elapsed.setObjectName("muted")
        self.elapsed.setFixedWidth(32)
        self.elapsed.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 0)
        self.progress.setToolTip("Posición")
        self.total = QLabel("0:00")
        self.total.setObjectName("muted")
        self.total.setFixedWidth(32)
        progress_row.addWidget(self.elapsed)
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.total)
        center.addLayout(progress_row)
        root.addLayout(center, 3)

        right = QHBoxLayout()
        right.setSpacing(7)
        volume_icon = QLabel("◖")
        volume_icon.setObjectName("muted")
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(82)
        self.volume.setFixedWidth(92)
        self.queue_button = QToolButton()
        self.queue_button.setObjectName("smallButton")
        self.queue_button.setText("☷")
        self.queue_button.setToolTip("Ver cola")
        self.queue_button.clicked.connect(lambda _checked=False: self.queueRequested.emit())
        right.addWidget(volume_icon)
        right.addWidget(self.volume)
        right.addWidget(self.queue_button)
        root.addLayout(right)

        self.play_button.clicked.connect(self.controller.play_pause)
        self.previous_button.clicked.connect(self.controller.previous)
        self.next_button.clicked.connect(self.controller.next)
        self.shuffle_button.clicked.connect(self._toggle_shuffle)
        self.repeat_button.clicked.connect(self._toggle_repeat)
        self.progress.sliderMoved.connect(self.controller.set_position)
        self.volume.valueChanged.connect(self.controller.set_volume)
        self.controller.currentChanged.connect(self.set_track)
        self.controller.playingChanged.connect(self._set_playing)
        self.controller.positionChanged.connect(self._set_position)

    @staticmethod
    def _transport(text: str, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName("transportButton")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def set_track(self, track: dict[str, Any] | None) -> None:
        if not track:
            return
        self._current_path = str(track.get("cover_path") or "")
        self.cover.setPixmap(self.cover_cache.pixmap(self._current_path, 56))
        self.title.setText(str(track.get("title", "Sin título")))
        self.artist.setText(str(track.get("artist", "Artista desconocido")))
        self.title.setToolTip(str(track.get("title", "")))
        self.artist.setToolTip(str(track.get("album", "")))

    def _set_playing(self, playing: bool) -> None:
        self.play_button.setText("Ⅱ" if playing else "▶")
        self.play_button.setToolTip("Pausar" if playing else "Reproducir")

    def _set_position(self, position: int, duration: int) -> None:
        if not self.progress.isSliderDown():
            self.progress.setRange(0, max(0, duration))
            self.progress.setValue(min(position, max(0, duration)))
        self.elapsed.setText(format_duration(position / 1000))
        self.total.setText(format_duration(duration / 1000))

    def _toggle_shuffle(self) -> None:
        enabled = self.controller.toggle_shuffle()
        self.shuffle_button.setProperty("active", enabled)
        self.shuffle_button.style().unpolish(self.shuffle_button)
        self.shuffle_button.style().polish(self.shuffle_button)
        self.shuffle_button.setToolTip("Aleatorio: activado" if enabled else "Aleatorio: desactivado")

    def _toggle_repeat(self) -> None:
        mode = self.controller.toggle_repeat()
        label = {"none": "↻", "all": "↻", "one": "↻¹"}[mode]
        self.repeat_button.setText(label)
        self.repeat_button.setProperty("active", mode != "none")
        self.repeat_button.style().unpolish(self.repeat_button)
        self.repeat_button.style().polish(self.repeat_button)
        self.repeat_button.setToolTip(
            {"none": "Repetir: desactivado", "all": "Repetir: cola", "one": "Repetir: canción"}[mode]
        )


class EmptyState(QWidget):
    def __init__(self, title: str, body: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 50, 30, 50)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QLabel(body)
        text.setObjectName("muted")
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setMaximumWidth(500)
        layout.addWidget(heading)
        layout.addSpacing(8)
        layout.addWidget(text)
