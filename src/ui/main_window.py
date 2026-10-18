"""Ventana principal con diseño Y2K Modular — Réplica visual de alta fidelidad."""

from __future__ import annotations

import math
import random
import tkinter as tk
import webbrowser
import customtkinter as ctk

from config.settings import AUDIUS_SEARCH_LIMIT
from src.audius import AudiusClient, AudiusError, AudiusTrack
from src.audius.models import format_duration
from src.player.controller import (
    STATE_ENDED, STATE_ERROR, STATE_IDLE, STATE_LOADING, STATE_PLAYING,
    PlaybackError, PlayerController, StreamSource
)
from src.ui import styles
from src.ui.background import BackgroundRunner
from src.ui.components import button, icon_button, panel, LibraryRow, PlaylistRow
from src.ui.icons import get_icon
from src.ui.image_loader import ImageLoader

SEARCH_HINT = "Buscar canciones, artistas, álbumes..."
DEFAULT_QUERY = "lofi chill"
TICK_MS = 300

ctk.set_appearance_mode("light")


class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("nova player ✦ retro · y2k · modular")
        self.geometry("1365x780")
        self.minsize(1120, 720)
        self.configure(fg_color=styles.BACKGROUND)
        self.query = ctk.StringVar()

        self.audius = AudiusClient()
        self.player = PlayerController()
        self.runner = BackgroundRunner(self)
        self.images = ImageLoader(self.runner)

        self.current_track: AudiusTrack | None = None
        self.selected_track: AudiusTrack | None = None
        self.current_playlist: list[AudiusTrack] = []
        
        self._search_token = 0
        self._play_token = 0
        self._last_state = ""
        self._is_seeking = False
        self._spectrum_phase = 0.0
        self._shuffle = False
        self._repeat = False
        self._shuffle_btns: list[ctk.CTkButton] = []
        self._repeat_btns: list[ctk.CTkButton] = []
        self.favorites: set[str] = set()
        self._tab_btns: dict[str, ctk.CTkButton] = {}
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        self.bb_fav_btn: ctk.CTkButton | None = None

        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Iniciar ticker
        self.after(TICK_MS, self._tick)

        # Cargar catálogo inicial para que la app se vea completa desde el primer segundo
        self.after(100, self._load_initial_tracks)

    def _build_layout(self) -> None:
        # Layout vertical: Barra superior (fila 0), Centro (fila 1, expande), Barra inferior (fila 2)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # 1. BARRA SUPERIOR
        self._build_top_bar()

        # 2. ÁREA CENTRAL MODULAR
        center_container = ctk.CTkFrame(self, fg_color="transparent")
        center_container.grid(row=1, column=0, sticky="nsew", padx=16, pady=(12, 12))
        center_container.grid_rowconfigure(0, weight=1)
        center_container.grid_columnconfigure(0, weight=0, minsize=210)  # Sidebar
        center_container.grid_columnconfigure(1, weight=1)              # Grid principal

        self._build_sidebar(center_container)
        self._build_content_grid(center_container)

        # 3. BARRA INFERIOR
        self._build_bottom_bar()

    # =========================================================================
    # 1. BARRA SUPERIOR (TOP BAR)
    # =========================================================================
    def _build_top_bar(self) -> None:
        top_bar = ctk.CTkFrame(self, height=48, fg_color=styles.TOP_BAR, corner_radius=0)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_propagate(False)
        top_bar.grid_columnconfigure(0, weight=1)
        top_bar.grid_columnconfigure(1, weight=2)
        top_bar.grid_columnconfigure(2, weight=1)
        top_bar.grid_rowconfigure(0, weight=1)

        # Izquierda: Logo y subtítulo
        left_tb = ctk.CTkFrame(top_bar, fg_color="transparent")
        left_tb.grid(row=0, column=0, sticky="w", padx=20)
        
        lbl_sparkle = ctk.CTkLabel(left_tb, text="✦", text_color=styles.ACCENT, font=ctk.CTkFont(size=14))
        lbl_sparkle.pack(side="left", padx=(0, 6))
        
        lbl_title = ctk.CTkLabel(left_tb, text="nova player", text_color=styles.TEXT_LIGHT, font=ctk.CTkFont(family=styles.FONT, size=15, weight="bold"))
        lbl_title.pack(side="left", padx=(0, 6))
        
        lbl_sparkle2 = ctk.CTkLabel(left_tb, text="✦", text_color=styles.ACCENT, font=ctk.CTkFont(size=14))
        lbl_sparkle2.pack(side="left", padx=(0, 10))

        lbl_sub = ctk.CTkLabel(left_tb, text="retro · y2k · modular", text_color=styles.MUTED_LIGHT, font=ctk.CTkFont(family=styles.FONT, size=11))
        lbl_sub.pack(side="left")

        # Centro: Píldora de búsqueda
        search_capsule = ctk.CTkFrame(top_bar, fg_color="#262940", border_width=1, border_color="#343854", corner_radius=18, height=34, width=420)
        search_capsule.grid(row=0, column=1)
        search_capsule.pack_propagate(False)

        self.search_entry = ctk.CTkEntry(
            search_capsule,
            textvariable=self.query,
            placeholder_text=SEARCH_HINT,
            fg_color="transparent",
            border_width=0,
            text_color=styles.TEXT_LIGHT,
            placeholder_text_color=styles.MUTED_LIGHT,
            font=ctk.CTkFont(family=styles.FONT, size=11),
            width=360,
            height=30
        )
        self.search_entry.pack(side="left", padx=(14, 0), fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda _e: self._search())

        btn_search = ctk.CTkButton(
            search_capsule,
            text="",
            image=get_icon("search", (14, 14), "muted"),
            width=28,
            height=28,
            fg_color="transparent",
            hover_color="#343854",
            corner_radius=14,
            command=self._search
        )
        btn_search.pack(side="right", padx=(0, 6))

        # Derecha: Avatar de gatito y controles de ventana
        right_tb = ctk.CTkFrame(top_bar, fg_color="transparent")
        right_tb.grid(row=0, column=2, sticky="e", padx=20)

        # Avatar gatito en badge
        cat_badge = ctk.CTkLabel(right_tb, text="", image=get_icon("cat", (28, 28)), width=32, height=32)
        cat_badge.pack(side="left", padx=(0, 16))

        # Controles ventana simulados
        ctk.CTkLabel(right_tb, text="—", text_color=styles.MUTED_LIGHT, font=ctk.CTkFont(size=12)).pack(side="left", padx=8)
        ctk.CTkLabel(right_tb, text="□", text_color=styles.MUTED_LIGHT, font=ctk.CTkFont(size=14)).pack(side="left", padx=8)
        close_badge = ctk.CTkLabel(right_tb, text="✕", fg_color=styles.ACCENT, text_color=styles.TEXT_LIGHT, width=22, height=22, corner_radius=6, font=ctk.CTkFont(size=11, weight="bold"))
        close_badge.pack(side="left", padx=(8, 0))

    # =========================================================================
    # 2. BARRA LATERAL (SIDEBAR)
    # =========================================================================
    def _build_sidebar(self, parent: ctk.CTkFrame) -> None:
        sidebar = panel(parent, width=210)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        sidebar.pack_propagate(False)

        # Sección NAVEGACIÓN
        nav_box = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_box.pack(fill="x", padx=12, pady=(16, 8))
        
        ctk.CTkLabel(
            nav_box, text="NAVEGACIÓN", text_color=styles.MUTED_TEXT, 
            font=ctk.CTkFont(family=styles.FONT, size=10, weight="bold")
        ).pack(anchor="w", padx=6, pady=(0, 8))

        nav_items = [
            ("home", "Inicio", True),
            ("compass", "Explorar", False),
            ("library", "Biblioteca", False),
            ("heart", "Favoritas", False),
            ("clock", "Recientes", False),
            ("download", "Descargas", False),
        ]

        for icon_name, text, is_active in nav_items:
            bg_col = styles.ACCENT_LIGHT if is_active else "transparent"
            text_col = styles.TEXT if is_active else styles.TEXT
            ic_col = "dark" if is_active else "muted"

            btn = ctk.CTkButton(
                nav_box,
                text=f"  {text}",
                image=get_icon(icon_name, (14, 14), ic_col),
                compound="left",
                anchor="w",
                fg_color=bg_col,
                text_color=text_col,
                hover_color=styles.SURFACE_HOVER,
                corner_radius=8,
                height=32,
                font=ctk.CTkFont(family=styles.FONT, size=11, weight="bold" if is_active else "normal"),
                command=lambda t=text: self._on_nav_click(t)
            )
            btn.pack(fill="x", pady=1)
            self._nav_btns[text] = btn

        # Separador suave
        ctk.CTkFrame(sidebar, height=1, fg_color=styles.BORDER).pack(fill="x", padx=16, pady=8)

        # Sección PLAYLISTS
        pl_box = ctk.CTkFrame(sidebar, fg_color="transparent")
        pl_box.pack(fill="x", padx=12, pady=(0, 8))

        pl_hdr = ctk.CTkFrame(pl_box, fg_color="transparent")
        pl_hdr.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkLabel(
            pl_hdr, text="PLAYLISTS", text_color=styles.MUTED_TEXT, 
            font=ctk.CTkFont(family=styles.FONT, size=10, weight="bold")
        ).pack(side="left")

        # Botón + para crear playlist
        icon_button(pl_hdr, "plus", size=(12, 12), color="muted", width=20, height=20).pack(side="right")

        playlists = [
            ("chill vibes", "32"),
            ("night drive", "18"),
            ("coding mode", "24"),
            ("lofi hip hop", "45"),
            ("gym", "27"),
        ]

        for pl_name, count in playlists:
            item_btn = ctk.CTkFrame(pl_box, fg_color="transparent", height=28)
            item_btn.pack(fill="x", pady=1)
            item_btn.pack_propagate(False)

            ic = ctk.CTkLabel(item_btn, text="", image=get_icon("sparkle", (10, 10), "muted"), width=16)
            ic.pack(side="left", padx=(6, 4))
            lbl = ctk.CTkLabel(item_btn, text=pl_name, text_color=styles.TEXT, font=ctk.CTkFont(family=styles.FONT, size=11), anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            cnt = ctk.CTkLabel(item_btn, text=count, text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=10))
            cnt.pack(side="right", padx=6)

            def make_handler(pn=pl_name, f=item_btn, labels=(lbl, cnt, ic)):
                f.bind("<Enter>", lambda _e: f.configure(fg_color=styles.SURFACE_HOVER))
                f.bind("<Leave>", lambda _e: f.configure(fg_color="transparent"))
                for w in (f, *labels):
                    w.bind("<Button-1>", lambda _e, name=pn: self._quick_playlist(name))
            make_handler(pl_name, item_btn)

        # Banner decorativo inferior
        card = ctk.CTkFrame(sidebar, fg_color=styles.ACCENT_LIGHT, corner_radius=12)
        card.pack(side="bottom", fill="x", padx=12, pady=16)

        card_in = ctk.CTkFrame(card, fg_color="transparent")
        card_in.pack(padx=12, pady=12)

        ctk.CTkLabel(card_in, text="", image=get_icon("cat", (28, 28))).pack(side="left", padx=(0, 10))
        txts = ctk.CTkFrame(card_in, fg_color="transparent")
        txts.pack(side="left")
        ctk.CTkLabel(txts, text="good music", text_color=styles.TEXT, font=ctk.CTkFont(family=styles.FONT, size=11, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(txts, text="good mood", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=10)).pack(anchor="w")

    # =========================================================================
    # 3. REJILLA DE CONTENIDO PRINCIPAL (CONTENT GRID)
    # =========================================================================
    def _build_content_grid(self, parent: ctk.CTkFrame) -> None:
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.grid(row=0, column=1, sticky="nsew")

        # 4 Columnas principales
        grid.grid_columnconfigure(0, weight=1, uniform="mid")
        grid.grid_columnconfigure(1, weight=1, uniform="mid")
        grid.grid_columnconfigure(2, weight=1, uniform="mid")
        grid.grid_columnconfigure(3, weight=1, minsize=290, uniform="mid")

        # 3 Filas:
        # Fila 0: Now Playing (cols 0-2) + Playlist (col 3)  (Fija/proporcional)
        # Fila 1: Tools Row (cols 0, 1, 2, 3) (Fija ~115px)
        # Fila 2: Biblioteca (cols 0-2) + Detalles (col 3) (Expande)
        grid.grid_rowconfigure(0, weight=0)
        grid.grid_rowconfigure(1, weight=0)
        grid.grid_rowconfigure(2, weight=1)

        # Fila 0: Hero Now Playing & Cola Playlist
        self._build_now_playing_panel(grid)
        self._build_playlist_panel(grid)

        # Fila 1: 4 Paneles de Herramientas (EQ, Spectrum, Mini Player, Audius)
        self._build_tools_row(grid)

        # Fila 2: Tabla de biblioteca y Detalles
        self._build_library_panel(grid)
        self._build_details_panel(grid)

    # -------------------------------------------------------------------------
    # PANEL: NOW PLAYING HERO (Cols 0-2, Row 0)
    # -------------------------------------------------------------------------
    def _build_now_playing_panel(self, parent: ctk.CTkFrame) -> None:
        p = panel(parent)
        p.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=(0, 6), pady=(0, 6))

        # Encabezado con píldora y onda sonora
        header = ctk.CTkFrame(p, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 6))

        badge = ctk.CTkFrame(header, fg_color=styles.ACCENT_LIGHT, corner_radius=10)
        badge.pack(side="left")
        ctk.CTkLabel(
            badge, text="NOW PLAYING ✦", text_color=styles.TEXT,
            font=ctk.CTkFont(family=styles.FONT, size=10, weight="bold")
        ).pack(padx=10, pady=3)

        ctk.CTkLabel(header, text="", image=get_icon("eq_bars", (18, 14), "muted")).pack(side="right")

        # Cuerpo central: Portada + Info + Espectro
        body = ctk.CTkFrame(p, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 6))

        # Portada estilo CD / Cassette spine
        cover_container = ctk.CTkFrame(body, fg_color="transparent")
        cover_container.pack(side="left", padx=(0, 16))

        self.np_cover = ctk.CTkLabel(
            cover_container,
            text="",
            image=get_icon("cat", (80, 80)),
            width=140,
            height=140,
            fg_color=styles.BORDER,
            corner_radius=12
        )
        self.np_cover.pack()

        # Datos de pista
        info_col = ctk.CTkFrame(body, fg_color="transparent")
        info_col.pack(side="left", fill="both", expand=True)

        self.np_title = ctk.CTkLabel(
            info_col,
            text="dreamy night ✦",
            text_color=styles.TEXT,
            font=ctk.CTkFont(family=styles.FONT, size=20, weight="bold"),
            anchor="w"
        )
        self.np_title.pack(fill="x")

        self.np_artist = ctk.CTkLabel(
            info_col,
            text="saiko",
            text_color=styles.MUTED_TEXT,
            font=ctk.CTkFont(family=styles.FONT, size=13),
            anchor="w"
        )
        self.np_artist.pack(fill="x", pady=(1, 2))

        self.np_album = ctk.CTkLabel(
            info_col,
            text="moon city lights",
            text_color=styles.MUTED_TEXT,
            font=ctk.CTkFont(family=styles.FONT, size=11),
            anchor="w"
        )
        self.np_album.pack(fill="x", pady=(0, 6))

        # Badges técnicos + botón de favorito
        badges_row = ctk.CTkFrame(info_col, fg_color="transparent")
        badges_row.pack(fill="x", pady=(0, 8))

        for badge_text in ["MP3", "320 kbps", "44.1 kHz"]:
            b = ctk.CTkFrame(badges_row, fg_color=styles.SURFACE, border_width=1, border_color=styles.BORDER, corner_radius=6)
            b.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(b, text=badge_text, text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=9, weight="bold")).pack(padx=8, pady=2)

        self.np_fav_btn = ctk.CTkButton(
            badges_row,
            text="",
            image=get_icon("heart", (14, 14), "muted"),
            width=28,
            height=26,
            corner_radius=6,
            fg_color="transparent",
            border_width=1,
            border_color=styles.BORDER,
            hover_color=styles.SURFACE_HOVER,
            command=self._toggle_favorite
        )
        self.np_fav_btn.pack(side="left", padx=6)

        # Gráfico Canvas de espectro animado
        self.np_spectrum_canvas = tk.Canvas(info_col, height=36, bg=styles.SURFACE, highlightthickness=0)
        self.np_spectrum_canvas.pack(fill="x", pady=(0, 2))

        # Barra de progreso y controles dentro de NOW PLAYING
        progress_area = ctk.CTkFrame(p, fg_color="transparent")
        progress_area.pack(fill="x", padx=16, pady=(0, 4))

        self.np_time_curr = ctk.CTkLabel(progress_area, text="0:00", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=10))
        self.np_time_curr.pack(side="left")

        self.np_slider = ctk.CTkSlider(
            progress_area,
            from_=0,
            to=100,
            height=8,
            fg_color=styles.BORDER,
            progress_color=styles.ACCENT_GREEN,
            button_color=styles.ACCENT_GREEN,
            button_hover_color=styles.ACCENT,
            button_corner_radius=6,
            button_length=12
        )
        self.np_slider.set(0)
        self.np_slider.pack(side="left", fill="x", expand=True, padx=10)
        self.np_slider.bind("<ButtonPress-1>", lambda _e: self._on_seek_start())
        self.np_slider.bind("<ButtonRelease-1>", lambda _e: self._on_seek_release(self.np_slider))

        self.np_time_total = ctk.CTkLabel(progress_area, text="0:00", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=10))
        self.np_time_total.pack(side="right")

        # Fila de botones de control
        ctrls_row = ctk.CTkFrame(p, fg_color="transparent")
        ctrls_row.pack(pady=(0, 10))

        b = icon_button(ctrls_row, "shuffle", size=(16, 16), color="muted", command=self._toggle_shuffle)
        b.pack(side="left", padx=8)
        self._shuffle_btns.append(b)
        icon_button(ctrls_row, "prev", size=(18, 18), color="dark", command=self._play_prev).pack(side="left", padx=8)

        # Botón Play/Pause Hero circular grande
        self.np_play_btn = ctk.CTkButton(
            ctrls_row,
            text="",
            image=get_icon("play", (18, 18), "dark"),
            width=46,
            height=46,
            corner_radius=23,
            fg_color="#FFFFFF",
            border_width=2,
            border_color=styles.ACCENT_GREEN,
            hover_color=styles.ACCENT_LIGHT,
            command=self._toggle_play
        )
        self.np_play_btn.pack(side="left", padx=12)

        icon_button(ctrls_row, "next", size=(18, 18), color="dark", command=self._play_next).pack(side="left", padx=8)
        b = icon_button(ctrls_row, "repeat", size=(16, 16), color="muted", command=self._toggle_repeat)
        b.pack(side="left", padx=8)
        self._repeat_btns.append(b)

    # -------------------------------------------------------------------------
    # PANEL: PLAYLIST QUEUE (Col 3, Row 0)
    # -------------------------------------------------------------------------
    def _build_playlist_panel(self, parent: ctk.CTkFrame) -> None:
        p = panel(parent)
        p.grid(row=0, column=3, sticky="nsew", padx=(6, 0), pady=(0, 6))

        # Encabezado
        hdr = ctk.CTkFrame(p, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            hdr, text="PLAYLIST: CHILL TIME ✦", text_color=styles.TEXT,
            font=ctk.CTkFont(family=styles.FONT, size=11, weight="bold")
        ).pack(side="left")

        actions = ctk.CTkFrame(hdr, fg_color="transparent")
        actions.pack(side="right")
        icon_button(actions, "plus", size=(12, 12), color="muted", width=22, height=22).pack(side="left", padx=1)
        icon_button(actions, "edit", size=(12, 12), color="muted", width=22, height=22).pack(side="left", padx=1)
        icon_button(actions, "more", size=(12, 12), color="muted", width=22, height=22).pack(side="left", padx=1)

        # Scrollable lista de canciones
        self.pl_scroll = ctk.CTkScrollableFrame(p, fg_color="transparent")
        self.pl_scroll.pack(fill="both", expand=True, padx=6, pady=2)

        # Footer con conteo y botón Limpiar
        footer = ctk.CTkFrame(p, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(4, 10))

        self.pl_count_lbl = ctk.CTkLabel(footer, text="0 canciones, 0:00", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=10))
        self.pl_count_lbl.pack(side="left")

        btn_limpiar = ctk.CTkButton(
            footer, text="Limpiar", width=60, height=24, corner_radius=12,
            fg_color=styles.SURFACE_HOVER, text_color=styles.TEXT, hover_color=styles.BORDER,
            font=ctk.CTkFont(family=styles.FONT, size=10),
            command=self._clear_playlist_queue
        )
        btn_limpiar.pack(side="right", padx=(4, 0))

        icon_button(footer, "queue", size=(12, 12), color="muted", width=24, height=24).pack(side="right")

    # -------------------------------------------------------------------------
    # FILA DE HERRAMIENTAS: 4 PANELES (Row 1)
    # -------------------------------------------------------------------------
    def _build_tools_row(self, parent: ctk.CTkFrame) -> None:
        # 1. EQUALIZER (Col 0)
        eq_panel = panel(parent)
        eq_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=4)
        eq_hdr = ctk.CTkFrame(eq_panel, fg_color="transparent")
        eq_hdr.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(eq_hdr, text="EQUALIZER", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=9, weight="bold")).pack(side="left")
        
        # Switch ON lima
        sw = ctk.CTkFrame(eq_hdr, fg_color=styles.ACCENT_GREEN, corner_radius=8, width=32, height=16)
        sw.pack(side="right")
        ctk.CTkLabel(sw, text="ON ●", text_color=styles.TEXT, font=ctk.CTkFont(size=8, weight="bold")).pack(padx=3)

        # 8 Sliders verticales mini simulados
        sliders_box = ctk.CTkFrame(eq_panel, fg_color="transparent")
        sliders_box.pack(fill="x", padx=10, pady=(2, 4))
        freqs = ["60", "170", "310", "600", "1K", "3K", "6K", "12K"]
        for f in freqs:
            col = ctk.CTkFrame(sliders_box, fg_color="transparent")
            col.pack(side="left", fill="both", expand=True)
            # Dot verde lima en línea
            line_f = ctk.CTkFrame(col, width=2, height=28, fg_color=styles.BORDER)
            line_f.pack()
            dot = ctk.CTkFrame(col, width=6, height=6, corner_radius=3, fg_color=styles.ACCENT_GREEN)
            dot.place(in_=line_f, relx=0.5, rely=random.uniform(0.2, 0.7), anchor="center")
            ctk.CTkLabel(col, text=f, text_color=styles.MUTED_TEXT, font=ctk.CTkFont(size=7)).pack()

        preset_lbl = ctk.CTkLabel(eq_panel, text="Preset: Soft Rock ▾", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(size=9))
        preset_lbl.pack(pady=(0, 6))

        # 2. SPECTRUM (Col 1)
        sp_panel = panel(parent)
        sp_panel.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        sp_hdr = ctk.CTkFrame(sp_panel, fg_color="transparent")
        sp_hdr.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(sp_hdr, text="SPECTRUM", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=9, weight="bold")).pack(side="left")

        self.sp_canvas = tk.Canvas(sp_panel, height=38, bg=styles.SURFACE, highlightthickness=0)
        self.sp_canvas.pack(fill="x", padx=10, pady=2)

        opts = ctk.CTkFrame(sp_panel, fg_color="transparent")
        opts.pack(pady=(0, 6))
        ctk.CTkLabel(opts, text="◉ Bar   ○ Line", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(size=9)).pack()

        # 3. MINI PLAYER (Col 2)
        mp_panel = panel(parent)
        mp_panel.grid(row=1, column=2, sticky="nsew", padx=4, pady=4)
        mp_hdr = ctk.CTkFrame(mp_panel, fg_color="transparent")
        mp_hdr.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(mp_hdr, text="MINI PLAYER", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=9, weight="bold")).pack(side="left")

        mp_body = ctk.CTkFrame(mp_panel, fg_color="transparent")
        mp_body.pack(fill="x", padx=10, pady=(0, 4))
        self.mp_cover = ctk.CTkLabel(mp_body, text="", image=get_icon("cat", (28, 28)), width=34, height=34, fg_color=styles.BORDER, corner_radius=6)
        self.mp_cover.pack(side="left", padx=(0, 6))

        mp_info = ctk.CTkFrame(mp_body, fg_color="transparent")
        mp_info.pack(side="left", fill="both", expand=True)
        self.mp_title = ctk.CTkLabel(mp_info, text="dreamy night", text_color=styles.TEXT, font=ctk.CTkFont(size=10, weight="bold"), anchor="w")
        self.mp_title.pack(fill="x")
        self.mp_artist = ctk.CTkLabel(mp_info, text="saiko", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(size=9), anchor="w")
        self.mp_artist.pack(fill="x")

        # Mini controles
        mp_ctrls = ctk.CTkFrame(mp_panel, fg_color="transparent")
        mp_ctrls.pack(pady=(0, 6))
        icon_button(mp_ctrls, "prev", size=(12, 12), color="dark", width=22, height=22, command=self._play_prev).pack(side="left", padx=2)
        self.mp_play_btn = icon_button(mp_ctrls, "play", size=(12, 12), color="dark", width=24, height=24, fg_color=styles.ACCENT_LIGHT, command=self._toggle_play)
        self.mp_play_btn.pack(side="left", padx=4)
        icon_button(mp_ctrls, "next", size=(12, 12), color="dark", width=22, height=22, command=self._play_next).pack(side="left", padx=2)

        # 4. AUDIUS INTEGRATION (Col 3)
        au_panel = panel(parent)
        au_panel.grid(row=1, column=3, sticky="nsew", padx=(4, 0), pady=4)
        au_hdr = ctk.CTkFrame(au_panel, fg_color="transparent")
        au_hdr.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(au_hdr, text="INTEGRACIÓN AUDIUS", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=9, weight="bold")).pack(side="left")
        
        badge_au = ctk.CTkFrame(au_hdr, fg_color=styles.SURFACE_HOVER, corner_radius=6)
        badge_au.pack(side="right")
        ctk.CTkLabel(badge_au, text="● Conectado", text_color=styles.ACCENT_GREEN, font=ctk.CTkFont(size=8, weight="bold")).pack(padx=4, pady=1)

        au_body = ctk.CTkFrame(au_panel, fg_color="transparent")
        au_body.pack(fill="x", padx=12, pady=(2, 6))

        au_txt = ctk.CTkFrame(au_body, fg_color="transparent")
        au_txt.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(au_txt, text="Buscar millones de tracks independientes.", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(size=9), wraplength=140, justify="left").pack(anchor="w")

        btn_au = ctk.CTkButton(
            au_txt, text="⌕ Buscar en Audius", width=120, height=22, corner_radius=11,
            fg_color=styles.ACCENT_LIGHT, text_color=styles.TEXT, hover_color=styles.ACCENT,
            font=ctk.CTkFont(size=9, weight="bold"), command=lambda: self.search_entry.focus()
        )
        btn_au.pack(anchor="w", pady=(4, 0))

        # Pixel cat mascot con audífonos
        ctk.CTkLabel(au_body, text="", image=get_icon("cat", (32, 32))).pack(side="right", padx=(4, 0))

    # -------------------------------------------------------------------------
    # PANEL: BIBLIOTECA (Cols 0-2, Row 2)
    # -------------------------------------------------------------------------
    def _build_library_panel(self, parent: ctk.CTkFrame) -> None:
        lib = panel(parent)
        lib.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=(0, 6), pady=(6, 0))

        # Barra de pestañas y filtro
        top_filter = ctk.CTkFrame(lib, fg_color="transparent")
        top_filter.pack(fill="x", padx=16, pady=(12, 6))

        tabs_box = ctk.CTkFrame(top_filter, fg_color="transparent")
        tabs_box.pack(side="left")

        self._tab_btns = {}
        for tab_name in ["Canciones", "Álbumes", "Artistas", "Géneros"]:
            btn = ctk.CTkButton(
                tabs_box, text=tab_name, width=80 if tab_name == "Canciones" else 70, height=26, corner_radius=13,
                fg_color=styles.ACCENT_LIGHT if tab_name == "Canciones" else "transparent",
                text_color=styles.TEXT if tab_name == "Canciones" else styles.MUTED_TEXT,
                hover_color=styles.SURFACE_HOVER,
                font=ctk.CTkFont(family=styles.FONT, size=10, weight="bold" if tab_name == "Canciones" else "normal"),
                command=lambda tn=tab_name: self._on_library_tab(tn)
            )
            btn.pack(side="left", padx=2)
            self._tab_btns[tab_name] = btn

        # Filtro de búsqueda rápida
        filter_entry = ctk.CTkEntry(
            top_filter, placeholder_text="Filtrar biblioteca...", width=160, height=26,
            corner_radius=13, fg_color=styles.SURFACE_HOVER, border_width=1, border_color=styles.BORDER,
            font=ctk.CTkFont(size=10)
        )
        filter_entry.pack(side="right")
        filter_entry.bind("<KeyRelease>", lambda _e: self._filter_library(filter_entry.get().strip().lower()))

        # Encabezado de columnas de tabla
        tbl_hdr = ctk.CTkFrame(lib, fg_color="transparent", height=24)
        tbl_hdr.pack(fill="x", padx=16, pady=(4, 2))
        tbl_hdr.grid_columnconfigure(0, weight=0, minsize=38)
        tbl_hdr.grid_columnconfigure(1, weight=4)
        tbl_hdr.grid_columnconfigure(2, weight=2)
        tbl_hdr.grid_columnconfigure(3, weight=2)
        tbl_hdr.grid_columnconfigure(4, weight=1)
        tbl_hdr.grid_columnconfigure(5, weight=1)
        tbl_hdr.grid_columnconfigure(6, weight=0, minsize=36)
        tbl_hdr.grid_columnconfigure(7, weight=0, minsize=36)

        cols = [
            (0, "#"),
            (1, "TÍTULO"),
            (2, "ARTISTA"),
            (3, "ÁLBUM"),
            (4, "DURACIÓN"),
            (5, "AÑADIDO"),
            (6, ""),
            (7, "")
        ]
        for col_idx, col_name in cols:
            ctk.CTkLabel(
                tbl_hdr, text=col_name, text_color=styles.MUTED_TEXT,
                font=ctk.CTkFont(family=styles.FONT, size=9, weight="bold")
            ).grid(row=0, column=col_idx, sticky="w", padx=8)

        ctk.CTkFrame(lib, height=1, fg_color=styles.BORDER).pack(fill="x", padx=16, pady=(2, 4))

        # Scroll de biblioteca
        self.library_scroll = ctk.CTkScrollableFrame(lib, fg_color="transparent")
        self.library_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.lib_message = ctk.CTkLabel(
            self.library_scroll,
            text="Explorando canciones de Audius...",
            text_color=styles.MUTED_TEXT,
            font=ctk.CTkFont(size=11)
        )
        self.lib_message.pack(pady=40)

    # -------------------------------------------------------------------------
    # PANEL: DETALLES DE CANCIÓN (Col 3, Row 2)
    # -------------------------------------------------------------------------
    def _build_details_panel(self, parent: ctk.CTkFrame) -> None:
        det = panel(parent, "DETALLES DE LA CANCIÓN")
        det.grid(row=2, column=3, sticky="nsew", padx=(6, 0), pady=(6, 0))

        content = ctk.CTkFrame(det, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=8)

        self.det_cover = ctk.CTkLabel(
            content, text="", image=get_icon("cat", (60, 60)), width=130, height=130,
            fg_color=styles.BORDER, corner_radius=10
        )
        self.det_cover.pack(pady=(4, 8))

        self.det_title = ctk.CTkLabel(content, text="dreamy night", text_color=styles.TEXT, font=ctk.CTkFont(family=styles.FONT, size=13, weight="bold"))
        self.det_title.pack()

        self.det_artist = ctk.CTkLabel(content, text="saiko", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=11))
        self.det_artist.pack()

        self.det_album = ctk.CTkLabel(content, text="moon city lights", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=10))
        self.det_album.pack(pady=(1, 4))

        self.det_genre = ctk.CTkLabel(content, text="2023 · Lo-fi / Chillwave", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(family=styles.FONT, size=10))
        self.det_genre.pack(pady=(0, 6))

        # Pills de tags
        tags_box = ctk.CTkFrame(content, fg_color="transparent")
        tags_box.pack(pady=4)
        for t in ["chill", "lofi", "night", "vibes"]:
            pill = ctk.CTkFrame(tags_box, fg_color=styles.SURFACE_HOVER, corner_radius=6)
            pill.pack(side="left", padx=2)
            ctk.CTkLabel(pill, text=t, text_color=styles.MUTED_TEXT, font=ctk.CTkFont(size=9)).pack(padx=6, pady=1)

        self.det_path = ctk.CTkLabel(content, text="Ruta: Audius Stream / saiko / dreamy night.mp3", text_color=styles.MUTED_TEXT, font=ctk.CTkFont(size=8), wraplength=220)
        self.det_path.pack(side="bottom", pady=4)

    # =========================================================================
    # 4. BARRA INFERIOR DE REPRODUCCIÓN (BOTTOM BAR)
    # =========================================================================
    def _build_bottom_bar(self) -> None:
        bar = ctk.CTkFrame(self, height=76, fg_color=styles.BOTTOM_BAR, corner_radius=0)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_propagate(False)

        bar.grid_rowconfigure(0, weight=1)
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=3)
        bar.grid_columnconfigure(2, weight=1)

        # Izquierda: Cover + Título + Favorito
        left_area = ctk.CTkFrame(bar, fg_color="transparent")
        left_area.grid(row=0, column=0, sticky="w", padx=20)

        # Logo mini marca
        brand_f = ctk.CTkFrame(left_area, fg_color="transparent")
        brand_f.pack(side="left", padx=(0, 14))
        ctk.CTkLabel(brand_f, text="nova ✦", text_color=styles.TEXT_LIGHT, font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(brand_f, text="player", text_color=styles.MUTED_LIGHT, font=ctk.CTkFont(size=9)).pack(anchor="w")

        self.bb_cover = ctk.CTkLabel(left_area, text="", image=get_icon("cat", (28, 28)), width=42, height=42, fg_color=styles.SURFACE, corner_radius=6)
        self.bb_cover.pack(side="left", padx=(0, 10))

        bb_txt = ctk.CTkFrame(left_area, fg_color="transparent")
        bb_txt.pack(side="left", padx=(0, 10))
        self.bb_title = ctk.CTkLabel(bb_txt, text="dreamy night", text_color=styles.TEXT_LIGHT, font=ctk.CTkFont(family=styles.FONT, size=11, weight="bold"), anchor="w")
        self.bb_title.pack(fill="x")
        self.bb_artist = ctk.CTkLabel(bb_txt, text="saiko", text_color=styles.MUTED_LIGHT, font=ctk.CTkFont(family=styles.FONT, size=10), anchor="w")
        self.bb_artist.pack(fill="x")

        self.bb_fav_btn = icon_button(left_area, "heart", size=(14, 14), color="muted", hover_color="#2A2E47", command=self._toggle_favorite)
        self.bb_fav_btn.pack(side="left")

        # Centro: Controles + Onda sonora de progreso
        mid_area = ctk.CTkFrame(bar, fg_color="transparent")
        mid_area.grid(row=0, column=1, sticky="nsew")

        # Fila de botones
        ctrls = ctk.CTkFrame(mid_area, fg_color="transparent")
        ctrls.pack(pady=(8, 2))

        b = icon_button(ctrls, "shuffle", size=(14, 14), color="muted", hover_color="#2A2E47", command=self._toggle_shuffle)
        b.pack(side="left", padx=8)
        self._shuffle_btns.append(b)
        icon_button(ctrls, "prev", size=(16, 16), color="light", hover_color="#2A2E47", command=self._play_prev).pack(side="left", padx=8)

        # Botón Play central
        self.bb_play_btn = ctk.CTkButton(
            ctrls, text="", image=get_icon("play", (16, 16), "dark"), width=34, height=34, corner_radius=17,
            fg_color="#FFFFFF", hover_color=styles.ACCENT_LIGHT, command=self._toggle_play
        )
        self.bb_play_btn.pack(side="left", padx=10)

        icon_button(ctrls, "next", size=(16, 16), color="light", hover_color="#2A2E47", command=self._play_next).pack(side="left", padx=8)
        b = icon_button(ctrls, "repeat", size=(14, 14), color="muted", hover_color="#2A2E47", command=self._toggle_repeat)
        b.pack(side="left", padx=8)
        self._repeat_btns.append(b)

        # Barra de progreso completa
        prog_row = ctk.CTkFrame(mid_area, fg_color="transparent")
        prog_row.pack(fill="x", padx=30, pady=(0, 8))

        self.bb_time = ctk.CTkLabel(prog_row, text="0:00", text_color=styles.MUTED_LIGHT, font=ctk.CTkFont(size=9))
        self.bb_time.pack(side="left")

        self.bb_slider = ctk.CTkSlider(
            prog_row, from_=0, to=100, height=6, fg_color="#343854",
            progress_color=styles.ACCENT_GREEN, button_color=styles.ACCENT_GREEN, button_hover_color=styles.ACCENT,
            button_corner_radius=5, button_length=10
        )
        self.bb_slider.set(0)
        self.bb_slider.pack(side="left", fill="x", expand=True, padx=8)
        self.bb_slider.bind("<ButtonPress-1>", lambda _e: self._on_seek_start())
        self.bb_slider.bind("<ButtonRelease-1>", lambda _e: self._on_seek_release(self.bb_slider))

        self.bb_length = ctk.CTkLabel(prog_row, text="0:00", text_color=styles.MUTED_LIGHT, font=ctk.CTkFont(size=9))
        self.bb_length.pack(side="right")

        # Derecha: Volumen + Auriculares + Lista
        right_area = ctk.CTkFrame(bar, fg_color="transparent")
        right_area.grid(row=0, column=2, sticky="e", padx=20)

        icon_button(right_area, "volume", size=(14, 14), color="muted", hover_color="#2A2E47").pack(side="left", padx=4)

        self.vol_slider = ctk.CTkSlider(
            right_area, from_=0, to=100, width=80, height=6, fg_color="#343854",
            progress_color=styles.ACCENT_GREEN, button_color=styles.ACCENT_GREEN, command=self._on_volume
        )
        self.vol_slider.set(int(self.player.volume * 100))
        self.vol_slider.pack(side="left", padx=4)

        icon_button(right_area, "headphones", size=(14, 14), color="muted", hover_color="#2A2E47").pack(side="left", padx=4)
        icon_button(right_area, "queue", size=(14, 14), color="muted", hover_color="#2A2E47").pack(side="left", padx=4)

    # =========================================================================
    # LÓGICA DE AUDIUS Y REPRODUCCIÓN
    # =========================================================================
    def _load_initial_tracks(self) -> None:
        """Carga automáticamente canciones lofi en el inicio para no mostrar una pantalla vacía."""
        self.runner.submit(
            self.audius.search_tracks, DEFAULT_QUERY, AUDIUS_SEARCH_LIMIT,
            on_success=lambda tracks: self._show_results(0, DEFAULT_QUERY, tracks, auto_select_first=True),
            on_error=lambda _err: None
        )

    def _search(self) -> None:
        query = self.search_entry.get().strip()
        if not query or query == SEARCH_HINT:
            return
        self._search_token += 1
        token = self._search_token
        self._clear_library()
        self.lib_message.configure(text=f"Buscando “{query}” en Audius...")
        self.lib_message.pack(pady=40)

        self.runner.submit(
            self.audius.search_tracks, query, AUDIUS_SEARCH_LIMIT,
            on_success=lambda tracks: self._show_results(token, query, tracks),
            on_error=lambda exc: self._search_failed(token, exc)
        )

    def _show_results(self, token: int, query: str, tracks: list[AudiusTrack], auto_select_first: bool = False) -> None:
        if token != self._search_token and token != 0:
            return
        self.current_playlist = tracks
        if not tracks:
            self._clear_library()
            self.lib_message.configure(text=f"Sin resultados para “{query}”.")
            self.lib_message.pack(pady=40)
            return
        if auto_select_first and self.current_track is None:
            # Preferir una pista normal (< 10 min); los sets largos no caben en el búfer de pygame.
            first = next((t for t in tracks if t.can_stream and 0 < (t.duration or 0) <= 600), tracks[0])
            self.selected_track = first
        self._render_lists()
        if auto_select_first and self.current_track is None:
            self._select_track(self.selected_track)
            self._update_now_playing_meta(self.selected_track)

    def _clear_library(self) -> None:
        """Borra las filas de la tabla, conservando el label de estado."""
        for w in self.library_scroll.winfo_children():
            if w is not self.lib_message:
                w.destroy()

    def _active_id(self) -> str | None:
        track = self.current_track or self.selected_track
        return track.id if track else None

    def _render_lists(self) -> None:
        """(Re)dibuja tabla de biblioteca y panel de playlist resaltando la pista activa."""
        tracks = self.current_playlist
        active_id = self._active_id()
        self.lib_message.pack_forget()
        self._clear_library()

        for i, track in enumerate(tracks):
            is_active = track.id == active_id
            LibraryRow(
                self.library_scroll,
                index=i + 1,
                track=track,
                on_play=self._play_track,
                on_select=self._select_track,
                is_playing=is_active
            ).pack(fill="x", pady=1)

        # Actualizar Playlist panel
        for w in self.pl_scroll.winfo_children():
            w.destroy()

        total_secs = 0
        for i, track in enumerate(tracks[:10]):
            is_active = track.id == active_id
            total_secs += track.duration or 0
            PlaylistRow(
                self.pl_scroll,
                index=i + 1,
                track=track,
                images=self.images,
                on_play=self._play_track,
                is_playing=is_active
            ).pack(fill="x", pady=1)

        mins = total_secs // 60
        secs = total_secs % 60
        self.pl_count_lbl.configure(text=f"{len(tracks[:10])} canciones, {mins}:{secs:02d}")

    def _search_failed(self, token: int, exc: BaseException) -> None:
        if token != self._search_token:
            return
        self.lib_message.configure(text=f"Error al conectar con Audius: {exc}")
        self.lib_message.pack(pady=40)

    def _select_track(self, track: AudiusTrack) -> None:
        self.selected_track = track
        self.det_title.configure(text=track.title[:30])
        self.det_artist.configure(text=track.artist[:30])
        self.det_album.configure(text=track.album or "moon city lights")
        self.det_genre.configure(text=f"{track.genre or 'Lo-fi / Chillwave'}")
        self.det_path.configure(text=f"Ruta: Audius Stream / {track.artist} / {track.title}.mp3")
        if track.artwork.available:
            self.images.load(track.artwork, 130, lambda img: self._set_cover(self.det_cover, img, track))

    def _play_track(self, track: AudiusTrack) -> None:
        if not track.can_stream or not self.player.can_stream:
            return
        self._play_token += 1
        token = self._play_token
        self.player.stop()
        self.current_track = track
        self._select_track(track)
        self._update_now_playing_meta(track, loading=True)

        def prepare() -> StreamSource:
            url = self.audius.get_stream_url(track)
            return self.player.prepare_stream(url)

        self.runner.submit(
            prepare,
            on_success=lambda source: self._start_playback(token, track, source),
            on_error=lambda exc: self._playback_failed(token, exc)
        )

    def _start_playback(self, token: int, track: AudiusTrack, source: StreamSource) -> None:
        if token != self._play_token:
            if source.buffer:
                source.buffer.close()
            return
        try:
            self.player.play_source(source, track.duration)
            self._update_now_playing_meta(track)
            self._refresh_row_states()
        except PlaybackError as exc:
            self._playback_failed(token, exc)

    def _playback_failed(self, token: int, exc: BaseException) -> None:
        if token != self._play_token:
            return
        self.player.stop()
        msg = str(exc) or "No se pudo reproducir la pista."
        self.np_artist.configure(text=f"⚠ {msg}", text_color=styles.ERROR)
        self.bb_artist.configure(text=f"⚠ {msg}")
        self.mp_artist.configure(text="⚠ Error")

    def _update_now_playing_meta(self, track: AudiusTrack, loading: bool = False) -> None:
        title = track.title[:34] + ("…" if len(track.title) > 34 else "")
        artist = "Cargando…" if loading else track.artist
        album = track.album or "moon city lights"
        dur_str = format_duration(track.duration)

        self.np_title.configure(text=f"{title} ✦")
        self.np_artist.configure(text=artist, text_color=styles.MUTED_TEXT)
        self.np_album.configure(text=album)
        self.np_time_total.configure(text=dur_str)

        self.mp_title.configure(text=title)
        self.mp_artist.configure(text=artist)

        self.bb_title.configure(text=title)
        self.bb_artist.configure(text=artist)
        self.bb_length.configure(text=dur_str)

        # Actualizar iconos de favorito
        is_fav = track.id in self.favorites
        fav_icon = "heart_filled" if is_fav else "heart"
        fav_col = "lime" if is_fav else "muted"
        self.np_fav_btn.configure(
            image=get_icon(fav_icon, (14, 14), fav_col),
            border_color=styles.ACCENT_GREEN if is_fav else styles.BORDER
        )
        if self.bb_fav_btn:
            self.bb_fav_btn.configure(image=get_icon(fav_icon, (14, 14), fav_col))

        if track.artwork.available:
            self.images.load(track.artwork, 140, lambda img: self._set_cover(self.np_cover, img, track))
            self.images.load(track.artwork, 34, lambda img: self._set_cover(self.mp_cover, img, track))
            self.images.load(track.artwork, 42, lambda img: self._set_cover(self.bb_cover, img, track))
            self.images.load(track.artwork, 130, lambda img: self._set_cover(self.det_cover, img, track))

    def _set_cover(self, widget, image, track_context=None) -> None:
        if track_context is None or track_context in (self.current_track, self.selected_track):
            widget.configure(image=image, text="")
            widget.image = image

    def _refresh_row_states(self) -> None:
        if self.current_playlist:
            self._render_lists()

    def _toggle_play(self) -> None:
        # 1) Si hay un stream cargado, pausar/reanudar.
        if self.player.toggle_pause():
            return
        # 2) Si no, reproducir la pista actual, la seleccionada o la primera de la lista.
        track = self.current_track or self.selected_track
        if track is None and self.current_playlist:
            track = next((t for t in self.current_playlist if t.can_stream), None)
        if track is not None:
            self._play_track(track)

    def _toggle_shuffle(self) -> None:
        self._shuffle = not self._shuffle
        icon = get_icon("shuffle", (16, 16), "lime" if self._shuffle else "muted")
        for b in self._shuffle_btns:
            b.configure(image=icon)

    def _toggle_repeat(self) -> None:
        self._repeat = not self._repeat
        icon = get_icon("repeat", (16, 16), "lime" if self._repeat else "muted")
        for b in self._repeat_btns:
            b.configure(image=icon)

    def _play_next(self) -> None:
        self._skip_track(1)

    def _play_prev(self) -> None:
        self._skip_track(-1)

    def _skip_track(self, direction: int) -> None:
        playable = [t for t in self.current_playlist if t.can_stream]
        if not playable:
            return
        # Retroceder con más de 3 s reproducidos reinicia la pista (como Spotify).
        if direction < 0 and self.current_track and self.player.position() > 3:
            self.player.seek(0)
            return
        if self._shuffle and len(playable) > 1:
            choices = [t for t in playable if t is not self.current_track]
            self._play_track(random.choice(choices))
            return
        ref = self.current_track or self.selected_track
        ids = [t.id for t in playable]
        idx = ids.index(ref.id) if ref and ref.id in ids else -1
        new_idx = idx + (1 if direction > 0 else -1)
        if self._repeat:
            new_idx %= len(playable)
        elif not 0 <= new_idx < len(playable):
            return
        self._play_track(playable[new_idx])

    def _quick_playlist(self, name: str) -> None:
        self.query.set(name)
        self._search()

    def _on_nav_click(self, item: str) -> None:
        for name, btn in self._nav_btns.items():
            active = (name == item)
            btn.configure(
                fg_color=styles.ACCENT_LIGHT if active else "transparent",
                font=ctk.CTkFont(family=styles.FONT, size=11, weight="bold" if active else "normal")
            )
        if item == "Explorar":
            self.search_entry.focus()
        elif item == "Inicio":
            self.query.set("lofi chill")
            self._search()
        elif item == "Favoritas":
            self._show_favorites()
        elif item == "Biblioteca":
            if self.current_playlist:
                self._render_lists()
            else:
                self.query.set("chill")
                self._search()

    def _show_favorites(self) -> None:
        if not self.favorites:
            self._clear_library()
            self.lib_message.configure(text="No tienes canciones favoritas aún. Haz clic en ♡ para añadir.")
            self.lib_message.pack(pady=40)
            return
        fav_tracks = [t for t in self.current_playlist if t.id in self.favorites]
        if not fav_tracks:
            self._clear_library()
            self.lib_message.configure(text=f"{len(self.favorites)} favorita(s) guardada(s). Busca canciones para verlas.")
            self.lib_message.pack(pady=40)
        else:
            self._show_results(self._search_token, "Favoritas", fav_tracks)

    def _toggle_favorite(self) -> None:
        track = self.current_track or self.selected_track
        if not track:
            return
        if track.id in self.favorites:
            self.favorites.remove(track.id)
            is_fav = False
        else:
            self.favorites.add(track.id)
            is_fav = True
        fav_icon = "heart_filled" if is_fav else "heart"
        fav_col = "lime" if is_fav else "muted"
        self.np_fav_btn.configure(
            image=get_icon(fav_icon, (14, 14), fav_col),
            border_color=styles.ACCENT_GREEN if is_fav else styles.BORDER
        )
        if self.bb_fav_btn:
            self.bb_fav_btn.configure(image=get_icon(fav_icon, (14, 14), fav_col))
        self._refresh_row_states()

    def _clear_playlist_queue(self) -> None:
        self.current_playlist = []
        for w in self.pl_scroll.winfo_children():
            w.destroy()
        self.pl_count_lbl.configure(text="0 canciones, 0:00")

    def _filter_library(self, term: str) -> None:
        if not self.current_playlist:
            return
        for w in self.library_scroll.winfo_children():
            if isinstance(w, LibraryRow):
                matches = not term or (term in w.track.title.lower() or term in w.track.artist.lower() or term in (w.track.album or "").lower())
                if matches:
                    w.pack(fill="x", pady=1)
                else:
                    w.pack_forget()

    def _on_library_tab(self, selected_tab: str) -> None:
        for name, btn in self._tab_btns.items():
            active = (name == selected_tab)
            btn.configure(
                fg_color=styles.ACCENT_LIGHT if active else "transparent",
                text_color=styles.TEXT if active else styles.MUTED_TEXT,
                font=ctk.CTkFont(family=styles.FONT, size=10, weight="bold" if active else "normal")
            )
        if selected_tab == "Canciones":
            self._filter_library("")
        elif selected_tab == "Álbumes":
            sorted_tracks = sorted(self.current_playlist, key=lambda t: (t.album or "").lower())
            self._show_results(self._search_token, "Álbumes", sorted_tracks)
        elif selected_tab == "Artistas":
            sorted_tracks = sorted(self.current_playlist, key=lambda t: t.artist.lower())
            self._show_results(self._search_token, "Artistas", sorted_tracks)
        elif selected_tab == "Géneros":
            sorted_tracks = sorted(self.current_playlist, key=lambda t: (t.genre or "").lower())
            self._show_results(self._search_token, "Géneros", sorted_tracks)

    def _on_volume(self, value: float) -> None:
        self.player.set_volume(int(value) / 100)

    def _on_seek_start(self, _event=None) -> None:
        self._is_seeking = True

    def _on_seek_release(self, slider_or_event=None) -> None:
        self._is_seeking = False
        if not self.player.stream_backend:
            return
        slider = None
        if isinstance(slider_or_event, ctk.CTkSlider):
            slider = slider_or_event
        elif slider_or_event is not None and hasattr(slider_or_event, "widget"):
            widget = slider_or_event.widget
            if hasattr(widget, "master") and isinstance(widget.master, ctk.CTkSlider):
                slider = widget.master
        if slider is None:
            slider = self.np_slider

        if length := self.player.length():
            target_sec = (slider.get() / 100) * length
            self.player.seek(target_sec)
            pct = slider.get()
            self.np_slider.set(pct)
            self.bb_slider.set(pct)
            t_str = format_duration(target_sec)
            self.np_time_curr.configure(text=t_str)
            self.bb_time.configure(text=t_str)

    # -------------------------------------------------------------------------
    # ANIMACIÓN DE ESPECTRO & TICKER
    # -------------------------------------------------------------------------
    def _draw_spectrum(self, is_playing: bool) -> None:
        self._spectrum_phase += 0.2
        # Now playing spectrum canvas
        c = self.np_spectrum_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w > 10 and h > 10:
            c.delete("all")
            num_bars = 28
            bw = (w - 10) / num_bars
            for i in range(num_bars):
                x = 5 + i * bw
                if is_playing:
                    val = 0.3 + 0.6 * math.sin(self._spectrum_phase + i * 0.4) ** 2
                else:
                    val = 0.2 + 0.1 * math.sin(i * 0.5) ** 2
                bh = val * (h - 6)
                y1 = h - bh
                # Barra lavanda con punta lima
                c.create_rectangle(x, y1, x + bw - 3, h, fill=styles.ACCENT, outline="")
                c.create_rectangle(x, y1, x + bw - 3, y1 + 3, fill=styles.ACCENT_GREEN, outline="")

        # Tools row spectrum canvas
        sp_c = self.sp_canvas
        sw = sp_c.winfo_width()
        sh = sp_c.winfo_height()
        if sw > 10 and sh > 10:
            sp_c.delete("all")
            bars = 20
            sbw = (sw - 10) / bars
            for i in range(bars):
                sx = 5 + i * sbw
                val = (0.2 + 0.7 * math.sin(self._spectrum_phase * 1.2 + i * 0.6) ** 2) if is_playing else 0.15
                sbh = val * (sh - 4)
                sp_c.create_rectangle(sx, sh - sbh, sx + sbw - 2, sh, fill=styles.ACCENT, outline="")

    def _tick(self) -> None:
        state = self.player.state()
        is_playing = state in (STATE_PLAYING, STATE_LOADING)
        
        # Actualizar iconos de Play/Pause
        play_icon_hero = get_icon("pause" if is_playing else "play", (18, 18), "dark")
        play_icon_bb = get_icon("pause" if is_playing else "play", (16, 16), "dark")
        play_icon_mp = get_icon("pause" if is_playing else "play", (12, 12), "dark")
        
        self.np_play_btn.configure(image=play_icon_hero)
        self.bb_play_btn.configure(image=play_icon_bb)
        self.mp_play_btn.configure(image=play_icon_mp)

        # Actualizar sliders
        pos, length = self.player.position(), self.player.length()
        if length and not self._is_seeking:
            pct = min(100, pos / length * 100)
            self.np_slider.set(pct)
            self.bb_slider.set(pct)
            self.np_time_total.configure(text=format_duration(length))
            self.bb_length.configure(text=format_duration(length))

        pos_str = format_duration(pos)
        self.np_time_curr.configure(text=pos_str)
        self.bb_time.configure(text=pos_str)

        # Espectro visual
        self._draw_spectrum(is_playing)

        if state != self._last_state:
            if state == STATE_ERROR:
                self.player.stop()
            elif state == STATE_ENDED:
                self.np_slider.set(100)
                self.bb_slider.set(100)
                self._play_next()
            self._last_state = state

        self.after(TICK_MS, self._tick)

    def _on_close(self) -> None:
        self.runner.shutdown()
        self.player.shutdown()
        self.audius.close()
        self.destroy()
