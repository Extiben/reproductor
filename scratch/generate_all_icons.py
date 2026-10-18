import os, sys, math
from PIL import Image, ImageDraw

ICONS_DIR = r"c:\Users\3243714\Desktop\desarrollos\ktomusic\assets\icons"
os.makedirs(ICONS_DIR, exist_ok=True)

# Palettes
NAVY = (32, 35, 55, 255)       # #202337
MUTED = (119, 119, 143, 255)   # #77778F
WHITE = (251, 249, 248, 255)   # #FBF9F8
LIME = (197, 217, 76, 255)     # #C5D94C
LAVENDER = (183, 173, 240, 255)# #B7ADF0

def get_canvas(size=128):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)

def make_play(color=NAVY):
    img, d = get_canvas()
    d.polygon([(46, 30), (46, 98), (96, 64)], fill=color)
    return img

def make_pause(color=NAVY):
    img, d = get_canvas()
    d.rounded_rectangle([38, 30, 54, 98], radius=6, fill=color)
    d.rounded_rectangle([74, 30, 90, 98], radius=6, fill=color)
    return img

def make_prev(color=NAVY):
    img, d = get_canvas()
    d.rounded_rectangle([28, 32, 38, 96], radius=4, fill=color)
    d.polygon([(92, 32), (46, 64), (92, 96)], fill=color)
    return img

def make_next(color=NAVY):
    img, d = get_canvas()
    d.polygon([(36, 32), (82, 64), (36, 96)], fill=color)
    d.rounded_rectangle([90, 32, 100, 96], radius=4, fill=color)
    return img

def make_shuffle(color=NAVY):
    img, d = get_canvas()
    # top arrow
    d.line([(28, 40), (52, 40), (76, 88), (100, 88)], fill=color, width=10)
    d.polygon([(94, 76), (106, 88), (94, 100)], fill=color)
    # bottom arrow
    d.line([(28, 88), (52, 88), (60, 72)], fill=color, width=10)
    d.line([(68, 56), (76, 40), (100, 40)], fill=color, width=10)
    d.polygon([(94, 28), (106, 40), (94, 52)], fill=color)
    return img

def make_repeat(color=NAVY):
    img, d = get_canvas()
    # loop rect
    d.arc([30, 36, 98, 92], 20, 340, fill=color, width=10)
    d.polygon([(88, 26), (104, 40), (88, 54)], fill=color)
    return img

def make_heart(color=NAVY, filled=False):
    img, d = get_canvas()
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

def make_search(color=NAVY):
    img, d = get_canvas()
    d.ellipse([26, 26, 76, 76], outline=color, width=10)
    d.line([(70, 70), (102, 102)], fill=color, width=12)
    return img

def make_home(color=NAVY):
    img, d = get_canvas()
    d.polygon([(64, 24), (24, 60), (32, 68), (64, 38), (96, 68), (104, 60)], fill=color)
    d.rounded_rectangle([34, 58, 94, 104], radius=6, outline=color, width=10)
    d.rounded_rectangle([52, 74, 76, 104], radius=4, fill=color)
    return img

def make_compass(color=NAVY):
    img, d = get_canvas()
    d.ellipse([22, 22, 106, 106], outline=color, width=10)
    d.polygon([(64, 36), (74, 64), (64, 92), (54, 64)], outline=color, width=6)
    d.polygon([(64, 36), (74, 64), (64, 64)], fill=color)
    return img

def make_library(color=NAVY):
    img, d = get_canvas()
    d.rounded_rectangle([28, 30, 46, 98], radius=4, outline=color, width=8)
    d.rounded_rectangle([52, 30, 70, 98], radius=4, outline=color, width=8)
    d.polygon([(78, 34), (96, 38), (84, 98), (68, 94)], outline=color)
    d.line([(80, 34), (84, 98)], fill=color, width=6)
    return img

def make_clock(color=NAVY):
    img, d = get_canvas()
    d.ellipse([22, 22, 106, 106], outline=color, width=10)
    d.line([(64, 64), (64, 38)], fill=color, width=10)
    d.line([(64, 64), (86, 64)], fill=color, width=10)
    return img

def make_download(color=NAVY):
    img, d = get_canvas()
    # Tray
    d.line([(26, 88), (26, 102), (102, 102), (102, 88)], fill=color, width=10)
    # Arrow
    d.line([(64, 26), (64, 82)], fill=color, width=10)
    d.polygon([(44, 66), (64, 86), (84, 66)], fill=color)
    return img

def make_plus(color=NAVY):
    img, d = get_canvas()
    d.line([(64, 28), (64, 100)], fill=color, width=12)
    d.line([(28, 64), (100, 64)], fill=color, width=12)
    return img

def make_sparkle(color=NAVY):
    img, d = get_canvas()
    points = [
        (64, 20), (74, 52), (108, 64), (74, 76),
        (64, 108), (54, 76), (20, 64), (54, 52)
    ]
    d.polygon(points, fill=color)
    return img

def make_volume(color=NAVY):
    img, d = get_canvas()
    d.polygon([(26, 48), (46, 48), (68, 30), (68, 98), (46, 80), (26, 80)], fill=color)
    d.arc([54, 46, 84, 82], 300, 60, fill=color, width=8)
    d.arc([46, 32, 102, 96], 300, 60, fill=color, width=8)
    return img

def make_headphones(color=NAVY):
    img, d = get_canvas()
    d.arc([28, 24, 100, 96], 180, 0, fill=color, width=10)
    d.rounded_rectangle([24, 60, 42, 98], radius=6, fill=color)
    d.rounded_rectangle([86, 60, 104, 98], radius=6, fill=color)
    return img

def make_queue(color=NAVY):
    img, d = get_canvas()
    for y in [38, 64, 90]:
        d.line([(44, y), (100, y)], fill=color, width=10)
        d.ellipse([26, y-5, 36, y+5], fill=color)
    return img

def make_more(color=NAVY):
    img, d = get_canvas()
    for x in [34, 64, 94]:
        d.ellipse([x-7, 57, x+7, 71], fill=color)
    return img

def make_edit(color=NAVY):
    img, d = get_canvas()
    d.polygon([(82, 28), (100, 46), (46, 100), (28, 100), (28, 82)], outline=color, width=8)
    d.line([(72, 38), (90, 56)], fill=color, width=8)
    return img

def make_eq_bars(color=NAVY):
    img, d = get_canvas()
    bars = [(30, 50, 44, 98), (52, 24, 66, 98), (74, 60, 88, 98), (96, 36, 110, 98)]
    for b in bars:
        d.rounded_rectangle(b, radius=4, fill=color)
    return img

def make_cat_avatar(bg=(251, 249, 248), outline=NAVY):
    # Cute cat icon badge
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Background rounded square
    d.rounded_rectangle([8, 8, 120, 120], radius=24, fill=bg, outline=LAVENDER, width=4)
    # Ears
    d.polygon([(36, 52), (48, 28), (62, 52)], fill=outline)
    d.polygon([(92, 52), (80, 28), (66, 52)], fill=outline)
    d.polygon([(40, 48), (48, 34), (56, 48)], fill=(255, 180, 200, 255))
    d.polygon([(88, 48), (80, 34), (72, 48)], fill=(255, 180, 200, 255))
    # Head
    d.ellipse([32, 44, 96, 96], fill=WHITE, outline=outline, width=6)
    # Eyes
    d.ellipse([46, 64, 54, 74], fill=outline)
    d.ellipse([74, 64, 82, 74], fill=outline)
    # Nose/Mouth
    d.polygon([(62, 76), (66, 76), (64, 79)], fill=(255, 150, 180, 255))
    d.arc([56, 76, 64, 84], 0, 180, fill=outline, width=3)
    d.arc([64, 76, 72, 84], 0, 180, fill=outline, width=3)
    # Whiskers
    d.line([(24, 68), (40, 70)], fill=outline, width=3)
    d.line([(24, 78), (40, 76)], fill=outline, width=3)
    d.line([(104, 68), (88, 70)], fill=outline, width=3)
    d.line([(104, 78), (88, 76)], fill=outline, width=3)
    return img

GENERATORS = {
    "play": make_play,
    "pause": make_pause,
    "prev": make_prev,
    "next": make_next,
    "shuffle": make_shuffle,
    "repeat": make_repeat,
    "heart": make_heart,
    "heart_filled": lambda c: make_heart(c, filled=True),
    "search": make_search,
    "home": make_home,
    "compass": make_compass,
    "library": make_library,
    "clock": make_clock,
    "download": make_download,
    "plus": make_plus,
    "sparkle": make_sparkle,
    "volume": make_volume,
    "headphones": make_headphones,
    "queue": make_queue,
    "more": make_more,
    "edit": make_edit,
    "eq_bars": make_eq_bars,
    "cat": lambda c: make_cat_avatar(),
}

# Generate in colors: dark (navy), light (white), lime, muted, lavender
COLORS = {
    "dark": NAVY,
    "light": WHITE,
    "lime": LIME,
    "muted": MUTED,
    "lavender": LAVENDER,
}

count = 0
for name, gen_fn in GENERATORS.items():
    for cname, col in COLORS.items():
        fname = f"{name}_{cname}.png" if cname != "dark" else f"{name}.png"
        path = os.path.join(ICONS_DIR, fname)
        img = gen_fn(col)
        # downsample with high quality Lanczos for super smooth anti-aliasing
        img_smooth = img.resize((48, 48), Image.Resampling.LANCZOS)
        img_smooth.save(path)
        count += 1

print(f"Generated {count} icons into {ICONS_DIR}")
