"""Gestor de iconos vectoriales para Nova Player.
Carga iconos PNG/SVG de 'assets/icons' o genera iconos nítidos con antialiasing vía Pillow.
Permite al usuario colocar sus propios iconos en assets/icons/ para personalización total.
"""

from __future__ import annotations

import os
from typing import Dict, Tuple
from PIL import Image, ImageDraw
import customtkinter as ctk

ICONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icons"))
os.makedirs(ICONS_DIR, exist_ok=True)

# Paletas de color
NAVY = (32, 35, 55, 255)        # #202337
MUTED = (119, 119, 143, 255)    # #77778F
WHITE = (251, 249, 248, 255)    # #FBF9F8
LIME = (197, 217, 76, 255)      # #C5D94C
LAVENDER = (183, 173, 240, 255) # #B7ADF0

COLOR_MAP = {
    "dark": NAVY,
    "navy": NAVY,
    "light": WHITE,
    "white": WHITE,
    "lime": LIME,
    "muted": MUTED,
    "lavender": LAVENDER,
}

_IMAGE_CACHE: Dict[Tuple[str, int, int, str], ctk.CTkImage] = {}


def _get_canvas(size: int = 128) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


# --- DIBUJADORES DE ICONOS ---

def _draw_play(color=NAVY):
    img, d = _get_canvas()
    d.polygon([(46, 30), (46, 98), (96, 64)], fill=color)
    return img

def _draw_pause(color=NAVY):
    img, d = _get_canvas()
    d.rounded_rectangle([38, 30, 54, 98], radius=6, fill=color)
    d.rounded_rectangle([74, 30, 90, 98], radius=6, fill=color)
    return img

def _draw_prev(color=NAVY):
    img, d = _get_canvas()
    d.rounded_rectangle([28, 32, 38, 96], radius=4, fill=color)
    d.polygon([(92, 32), (46, 64), (92, 96)], fill=color)
    return img

def _draw_next(color=NAVY):
    img, d = _get_canvas()
    d.polygon([(36, 32), (82, 64), (36, 96)], fill=color)
    d.rounded_rectangle([90, 32, 100, 96], radius=4, fill=color)
    return img

def _draw_shuffle(color=NAVY):
    img, d = _get_canvas()
    d.line([(28, 40), (52, 40), (76, 88), (100, 88)], fill=color, width=10)
    d.polygon([(94, 76), (106, 88), (94, 100)], fill=color)
    d.line([(28, 88), (52, 88), (60, 72)], fill=color, width=10)
    d.line([(68, 56), (76, 40), (100, 40)], fill=color, width=10)
    d.polygon([(94, 28), (106, 40), (94, 52)], fill=color)
    return img

def _draw_repeat(color=NAVY):
    img, d = _get_canvas()
    d.arc([30, 36, 98, 92], 20, 340, fill=color, width=10)
    d.polygon([(88, 26), (104, 40), (88, 54)], fill=color)
    return img

def _draw_heart(color=NAVY, filled=False):
    img, d = _get_canvas()
    if filled:
        d.pieslice([24, 28, 70, 74], 180, 0, fill=color)
        d.pieslice([58, 28, 104, 74], 180, 0, fill=color)
        d.polygon([(24, 51), (104, 51), (64, 102)], fill=color)
    else:
        d.arc([24, 28, 70, 74], 180, 0, fill=color, width=10)
        d.arc([58, 28, 104, 74], 180, 0, fill=color, width=10)
        d.line([(24, 51), (64, 102)], fill=color, width=10)
        d.line([(104, 51), (64, 102)], fill=color, width=10)
    return img

def _draw_search(color=NAVY):
    img, d = _get_canvas()
    d.ellipse([26, 26, 76, 76], outline=color, width=10)
    d.line([(70, 70), (102, 102)], fill=color, width=12)
    return img

def _draw_home(color=NAVY):
    img, d = _get_canvas()
    d.polygon([(64, 24), (24, 60), (32, 68), (64, 38), (96, 68), (104, 60)], fill=color)
    d.rounded_rectangle([34, 58, 94, 104], radius=6, outline=color, width=10)
    d.rounded_rectangle([52, 74, 76, 104], radius=4, fill=color)
    return img

def _draw_compass(color=NAVY):
    img, d = _get_canvas()
    d.ellipse([22, 22, 106, 106], outline=color, width=10)
    d.polygon([(64, 36), (74, 64), (64, 92), (54, 64)], outline=color, width=6)
    d.polygon([(64, 36), (74, 64), (64, 64)], fill=color)
    return img

def _draw_library(color=NAVY):
    img, d = _get_canvas()
    d.rounded_rectangle([28, 30, 46, 98], radius=4, outline=color, width=8)
    d.rounded_rectangle([52, 30, 70, 98], radius=4, outline=color, width=8)
    d.polygon([(78, 34), (96, 38), (84, 98), (68, 94)], outline=color)
    d.line([(80, 34), (84, 98)], fill=color, width=6)
    return img

def _draw_clock(color=NAVY):
    img, d = _get_canvas()
    d.ellipse([22, 22, 106, 106], outline=color, width=10)
    d.line([(64, 64), (64, 38)], fill=color, width=10)
    d.line([(64, 64), (86, 64)], fill=color, width=10)
    return img

def _draw_download(color=NAVY):
    img, d = _get_canvas()
    d.line([(26, 88), (26, 102), (102, 102), (102, 88)], fill=color, width=10)
    d.line([(64, 26), (64, 82)], fill=color, width=10)
    d.polygon([(44, 66), (64, 86), (84, 66)], fill=color)
    return img

def _draw_plus(color=NAVY):
    img, d = _get_canvas()
    d.line([(64, 28), (64, 100)], fill=color, width=12)
    d.line([(28, 64), (100, 64)], fill=color, width=12)
    return img

def _draw_sparkle(color=NAVY):
    img, d = _get_canvas()
    points = [
        (64, 20), (74, 52), (108, 64), (74, 76),
        (64, 108), (54, 76), (20, 64), (54, 52)
    ]
    d.polygon(points, fill=color)
    return img

def _draw_volume(color=NAVY):
    img, d = _get_canvas()
    d.polygon([(26, 48), (46, 48), (68, 30), (68, 98), (46, 80), (26, 80)], fill=color)
    d.arc([54, 46, 84, 82], 300, 60, fill=color, width=8)
    d.arc([46, 32, 102, 96], 300, 60, fill=color, width=8)
    return img

def _draw_headphones(color=NAVY):
    img, d = _get_canvas()
    d.arc([28, 24, 100, 96], 180, 0, fill=color, width=10)
    d.rounded_rectangle([24, 60, 42, 98], radius=6, fill=color)
    d.rounded_rectangle([86, 60, 104, 98], radius=6, fill=color)
    return img

def _draw_queue(color=NAVY):
    img, d = _get_canvas()
    for y in [38, 64, 90]:
        d.line([(44, y), (100, y)], fill=color, width=10)
        d.ellipse([26, y-5, 36, y+5], fill=color)
    return img

def _draw_more(color=NAVY):
    img, d = _get_canvas()
    for x in [34, 64, 94]:
        d.ellipse([x-7, 57, x+7, 71], fill=color)
    return img

def _draw_edit(color=NAVY):
    img, d = _get_canvas()
    d.polygon([(82, 28), (100, 46), (46, 100), (28, 100), (28, 82)], outline=color, width=8)
    d.line([(72, 38), (90, 56)], fill=color, width=8)
    return img

def _draw_eq_bars(color=NAVY):
    img, d = _get_canvas()
    bars = [(30, 50, 44, 98), (52, 24, 66, 98), (74, 60, 88, 98), (96, 36, 110, 98)]
    for b in bars:
        d.rounded_rectangle(b, radius=4, fill=color)
    return img

def _draw_cat(color=NAVY):
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, 120, 120], radius=24, fill=WHITE, outline=LAVENDER, width=4)
    d.polygon([(36, 52), (48, 28), (62, 52)], fill=NAVY)
    d.polygon([(92, 52), (80, 28), (66, 52)], fill=NAVY)
    d.polygon([(40, 48), (48, 34), (56, 48)], fill=(255, 180, 200, 255))
    d.polygon([(88, 48), (80, 34), (72, 48)], fill=(255, 180, 200, 255))
    d.ellipse([32, 44, 96, 96], fill=WHITE, outline=NAVY, width=6)
    d.ellipse([46, 64, 54, 74], fill=NAVY)
    d.ellipse([74, 64, 82, 74], fill=NAVY)
    d.polygon([(62, 76), (66, 76), (64, 79)], fill=(255, 150, 180, 255))
    d.arc([56, 76, 64, 84], 0, 180, fill=NAVY, width=3)
    d.arc([64, 76, 72, 84], 0, 180, fill=NAVY, width=3)
    d.line([(24, 68), (40, 70)], fill=NAVY, width=3)
    d.line([(24, 78), (40, 76)], fill=NAVY, width=3)
    d.line([(104, 68), (88, 70)], fill=NAVY, width=3)
    d.line([(104, 78), (88, 76)], fill=NAVY, width=3)
    return img


_DRAWERS = {
    "play": _draw_play,
    "pause": _draw_pause,
    "prev": _draw_prev,
    "next": _draw_next,
    "shuffle": _draw_shuffle,
    "repeat": _draw_repeat,
    "heart": _draw_heart,
    "heart_filled": lambda c: _draw_heart(c, filled=True),
    "search": _draw_search,
    "home": _draw_home,
    "compass": _draw_compass,
    "library": _draw_library,
    "clock": _draw_clock,
    "download": _draw_download,
    "plus": _draw_plus,
    "sparkle": _draw_sparkle,
    "volume": _draw_volume,
    "headphones": _draw_headphones,
    "queue": _draw_queue,
    "more": _draw_more,
    "edit": _draw_edit,
    "eq_bars": _draw_eq_bars,
    "cat": lambda c: _draw_cat(),
}


def get_icon(name: str, size: Tuple[int, int] = (20, 20), color: str = "dark") -> ctk.CTkImage:
    """Obtiene un CTkImage limpio y antialiaseado para el icono especificado."""
    cache_key = (name, size[0], size[1], color)
    if cache_key in _IMAGE_CACHE:
        return _IMAGE_CACHE[cache_key]

    # 1. Comprobar si existe archivo en assets/icons
    filename = f"{name}_{color}.png" if color != "dark" else f"{name}.png"
    filepath = os.path.join(ICONS_DIR, filename)
    altpath = os.path.join(ICONS_DIR, f"{name}.png")

    img: Image.Image | None = None
    if os.path.exists(filepath):
        try:
            img = Image.open(filepath).convert("RGBA")
        except Exception:
            img = None
    elif os.path.exists(altpath):
        try:
            img = Image.open(altpath).convert("RGBA")
        except Exception:
            img = None

    # 2. Si no existe archivo físico, generarlo dinámicamente
    if img is None:
        drawer = _DRAWERS.get(name, _draw_sparkle)
        col = COLOR_MAP.get(color, NAVY)
        raw_img = drawer(col)
        # Redimensionar con Lanczos
        img = raw_img.resize((size[0] * 2, size[1] * 2), Image.Resampling.LANCZOS)
        try:
            img.save(filepath)
        except Exception:
            pass

    # Redimensionar al tamaño final
    scaled = img.resize(size, Image.Resampling.LANCZOS)
    ctk_img = ctk.CTkImage(light_image=scaled, dark_image=scaled, size=size)
    _IMAGE_CACHE[cache_key] = ctk_img
    return ctk_img
