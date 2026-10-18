"""Widgets reutilizables con CustomTkinter para Nova Player Y2K."""

from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING, Callable
from src.ui import styles
from src.ui.icons import get_icon

if TYPE_CHECKING:
    from src.audius.models import AudiusTrack
    from src.ui.image_loader import ImageLoader


def button(parent, text: str = "", command=None, *, accent: bool = False, icon: str | None = None, icon_size=(16, 16), **kwargs) -> ctk.CTkButton:
    background = styles.ACCENT if accent else styles.SURFACE_HOVER
    foreground = "#000000" if accent else styles.TEXT
    hover_color = styles.ACCENT_LIGHT if accent else styles.BORDER
    
    img = get_icon(icon, size=icon_size, color="dark" if not accent else "dark") if icon else None
    
    return ctk.CTkButton(
        parent,
        text=text,
        image=img,
        command=command,
        fg_color=background,
        text_color=foreground,
        hover_color=hover_color,
        corner_radius=8,
        font=ctk.CTkFont(family=styles.FONT, size=12, weight="bold"),
        **kwargs
    )


def icon_button(parent, icon_name: str, command=None, size=(16, 16), color="dark", hover_color=styles.SURFACE_HOVER, width=32, height=32, corner_radius=8, fg_color="transparent", **kwargs) -> ctk.CTkButton:
    """Botón compacto con icono puro y sin texto."""
    img = get_icon(icon_name, size=size, color=color)
    return ctk.CTkButton(
        parent,
        text="",
        image=img,
        width=width,
        height=height,
        corner_radius=corner_radius,
        fg_color=fg_color,
        hover_color=hover_color,
        command=command,
        **kwargs
    )


def panel(parent, title: str = "", **kwargs) -> ctk.CTkFrame:
    """Crea un panel modular estándar con bordes redondeados y estilo Y2K."""
    frm = ctk.CTkFrame(parent, fg_color=styles.SURFACE, corner_radius=16, border_width=1, border_color=styles.BORDER, **kwargs)
    if title:
        header = ctk.CTkFrame(frm, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(
            header,
            text=title.upper(),
            text_color=styles.MUTED_TEXT, 
            font=ctk.CTkFont(family=styles.FONT, size=10, weight="bold")
        ).pack(side="left")
    return frm


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class LibraryRow(ctk.CTkFrame):
    """Fila para la tabla de la biblioteca musical."""

    def __init__(
        self,
        parent,
        index: int,
        track: "AudiusTrack",
        on_play: Callable[["AudiusTrack"], None],
        on_select: Callable[["AudiusTrack"], None],
        is_playing: bool = False,
    ) -> None:
        super().__init__(parent, fg_color=styles.ACCENT_LIGHT if is_playing else "transparent", corner_radius=6, height=38)
        self.pack_propagate(False)
        self.track = track
        self.is_playing = is_playing

        self.bind("<Button-1>", lambda e: on_select(track))
        
        # Grid columns
        self.grid_columnconfigure(0, weight=0, minsize=38)  # #
        self.grid_columnconfigure(1, weight=4)              # Título
        self.grid_columnconfigure(2, weight=2)              # Artista
        self.grid_columnconfigure(3, weight=2)              # Álbum
        self.grid_columnconfigure(4, weight=1)              # Duración
        self.grid_columnconfigure(5, weight=1)              # Fecha
        self.grid_columnconfigure(6, weight=0, minsize=36)  # Favorito
        self.grid_columnconfigure(7, weight=0, minsize=36)  # Opciones

        # 1. Index / Play indicator
        self.idx_frame = ctk.CTkFrame(self, fg_color="transparent", width=38, height=34)
        self.idx_frame.grid(row=0, column=0, padx=(8, 2), pady=2)
        
        if is_playing:
            self.idx_lbl = ctk.CTkLabel(self.idx_frame, text="", image=get_icon("eq_bars", (14, 14), "lime"), width=24)
        else:
            self.idx_lbl = ctk.CTkLabel(self.idx_frame, text=f"{index:02d}", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=11))
        self.idx_lbl.pack(expand=True)

        # 2. Título
        title_lbl = ctk.CTkLabel(
            self,
            text=_shorten(track.title, 38),
            text_color=styles.TEXT, 
            font=ctk.CTkFont(family=styles.FONT, size=11, weight="bold" if is_playing else "normal"),
            anchor="w"
        )
        title_lbl.grid(row=0, column=1, sticky="ew", padx=8)

        # 3. Artista
        art_lbl = ctk.CTkLabel(
            self,
            text=_shorten(track.artist, 26),
            text_color=styles.MUTED_TEXT,
            anchor="w",
            font=ctk.CTkFont(family=styles.FONT, size=11)
        )
        art_lbl.grid(row=0, column=2, sticky="ew", padx=8)

        # 4. Álbum
        alb_lbl = ctk.CTkLabel(
            self,
            text=_shorten(track.album or "Single", 22),
            text_color=styles.MUTED_TEXT,
            anchor="w",
            font=ctk.CTkFont(family=styles.FONT, size=11)
        )
        alb_lbl.grid(row=0, column=3, sticky="ew", padx=8)

        # 5. Duración
        dur_lbl = ctk.CTkLabel(
            self,
            text=track.duration_label if track.duration else "--:--", 
            text_color=styles.MUTED_TEXT,
            font=ctk.CTkFont(family=styles.FONT, size=11)
        )
        dur_lbl.grid(row=0, column=4, padx=8)

        # 6. Añadido
        date_lbl = ctk.CTkLabel(
            self,
            text="09/05/2024",
            text_color=styles.MUTED_TEXT,
            font=ctk.CTkFont(family=styles.FONT, size=10)
        )
        date_lbl.grid(row=0, column=5, padx=8)

        # 7. Favorito ♡
        fav_icon = "heart_filled" if is_playing else "heart"
        fav_col = "lime" if is_playing else "muted"
        self.fav_btn = ctk.CTkLabel(self, text="", image=get_icon(fav_icon, (14, 14), fav_col), width=24)
        self.fav_btn.grid(row=0, column=6, padx=4)

        # 8. Opciones ...
        more_lbl = ctk.CTkLabel(self, text="", image=get_icon("more", (14, 14), "muted"), width=24)
        more_lbl.grid(row=0, column=7, padx=(4, 8))

        # Hover effect
        def on_enter(e):
            if not self.is_playing:
                self.configure(fg_color=styles.SURFACE_HOVER)
                self.idx_lbl.configure(text="", image=get_icon("play", (12, 12), "dark"))

        def on_leave(e):
            if not self.is_playing:
                self.configure(fg_color="transparent")
                self.idx_lbl.configure(text=f"{index:02d}", image=None)

        self.bind("<Enter>", on_enter)
        self.bind("<Leave>", on_leave)
        
        # Click handlers
        for w in (title_lbl, art_lbl, alb_lbl, dur_lbl, date_lbl):
            w.bind("<Button-1>", lambda e: on_select(track))
            w.bind("<Double-Button-1>", lambda e: on_play(track))
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

        self.idx_frame.bind("<Button-1>", lambda e: on_play(track) if track.can_stream else None)
        self.idx_lbl.bind("<Button-1>", lambda e: on_play(track) if track.can_stream else None)


class PlaylistRow(ctk.CTkFrame):
    """Fila compacta para el panel de playlist de la esquina superior derecha."""

    COVER_SIZE = 36

    def __init__(
        self,
        parent,
        index: int,
        track: "AudiusTrack",
        images: "ImageLoader",
        on_play: Callable[["AudiusTrack"], None],
        is_playing: bool = False,
    ) -> None:
        bg = styles.ACCENT_LIGHT if is_playing else "transparent"
        super().__init__(parent, fg_color=bg, corner_radius=8, height=44)
        self.pack_propagate(False)
        self.track = track
        self.is_playing = is_playing
        
        self.grid_columnconfigure(2, weight=1)
        
        # 1. Index
        self.idx_lbl = ctk.CTkLabel(self, text=str(index), text_color=styles.TEXT if is_playing else styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=11, weight="bold" if is_playing else "normal"))
        self.idx_lbl.grid(row=0, column=0, padx=(8, 4), pady=4)
        
        # 2. Cover
        self.cover = ctk.CTkLabel(self, text="", width=self.COVER_SIZE, height=self.COVER_SIZE, fg_color=styles.BORDER, corner_radius=6)
        self.cover.grid(row=0, column=1, padx=4, pady=4)
        if track.artwork.available:
            images.load(track.artwork, self.COVER_SIZE, self._set_cover)
            
        # 3. Info (Title + Artist)
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=2, sticky="ew", padx=6)
        lbl_title = ctk.CTkLabel(info, text=_shorten(track.title, 22), text_color=styles.TEXT, font=ctk.CTkFont(family=styles.FONT, size=11, weight="bold"), anchor="w")
        lbl_title.pack(fill="x")
        ctk.CTkLabel(info, text=_shorten(track.artist, 20), text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=10), anchor="w").pack(fill="x")
        
        # 4. Right side: Heart + Duration + (EQ if playing or more if not)
        right_info = ctk.CTkFrame(self, fg_color="transparent")
        right_info.grid(row=0, column=3, padx=(4, 8))
        
        fav_icon = "heart_filled" if is_playing else "heart"
        fav_col = "lime" if is_playing else "muted"
        ctk.CTkLabel(right_info, text="", image=get_icon(fav_icon, (12, 12), fav_col), width=18).pack(side="left", padx=2)
        
        ctk.CTkLabel(right_info, text=track.duration_label if track.duration else "--:--", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=10)).pack(side="left", padx=3)

        if is_playing:
            ctk.CTkLabel(right_info, text="", image=get_icon("eq_bars", (12, 12), "lime"), width=18).pack(side="left", padx=2)
        else:
            ctk.CTkLabel(right_info, text="", image=get_icon("more", (12, 12), "muted"), width=18).pack(side="left", padx=2)

        # Play bind
        for w in (self, lbl_title, self.cover):
            w.bind("<Button-1>", lambda e: on_play(track))

        def on_enter(e):
            if not self.is_playing:
                self.configure(fg_color=styles.SURFACE_HOVER)
        def on_leave(e):
            if not self.is_playing:
                self.configure(fg_color="transparent")

        self.bind("<Enter>", on_enter)
        self.bind("<Leave>", on_leave)

    def _set_cover(self, image) -> None:
        self.cover.configure(image=image)
        self.cover.image = image
