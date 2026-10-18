import os, sys
from PIL import Image, ImageDraw

ICONS_DIR = r"c:\Users\3243714\Desktop\desarrollos\ktomusic\assets\icons"
os.makedirs(ICONS_DIR, exist_ok=True)

def create_canvas(size=128):
    return Image.new("RGBA", (size, size), (0, 0, 0, 0)), ImageDraw.Draw(Image.new("RGBA", (size, size), (0, 0, 0, 0)))

def draw_play(color=(32, 35, 55)):
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # triangle
    points = [(42, 28), (42, 100), (98, 64)]
    d.polygon(points, fill=color)
    return img

def draw_pause(color=(32, 35, 55)):
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([36, 28, 54, 100], radius=4, fill=color)
    d.rounded_rectangle([74, 28, 92, 100], radius=4, fill=color)
    return img

def draw_prev(color=(32, 35, 55)):
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([28, 32, 38, 96], radius=3, fill=color)
    d.polygon([(92, 32), (44, 64), (92, 96)], fill=color)
    return img

def draw_next(color=(32, 35, 55)):
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(36, 32), (84, 64), (36, 96)], fill=color)
    d.rounded_rectangle([90, 32, 100, 96], radius=3, fill=color)
    return img

def draw_heart(color=(32, 35, 55), filled=False):
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 2 circles + polygon
    # left circle center (46, 50), r=24
    # right circle center (82, 50), r=24
    # bottom point (64, 104)
    # Or bezier/lines
    if filled:
        d.pieslice([22, 26, 70, 74], 180, 0, fill=color)
        d.pieslice([58, 26, 106, 74], 180, 0, fill=color)
        d.polygon([(22, 50), (106, 50), (64, 104)], fill=color)
    else:
        # outline
        d.arc([22, 26, 70, 74], 180, 0, fill=color, width=8)
        d.arc([58, 26, 106, 74], 180, 0, fill=color, width=8)
        d.line([(22, 50), (64, 104)], fill=color, width=8)
        d.line([(106, 50), (64, 104)], fill=color, width=8)
    return img

def draw_cat(color=(32, 35, 55)):
    # 16x16 pixel art cat scaled up
    grid = [
        "  XX      XX  ",
        " X..X    X..X ",
        "X....XXXX....X",
        "X............X",
        "X..XX....XX..X",
        "X..XX....XX..X",
        "X............X",
        "X....X..X....X",
        " X....XX....X ",
        "  XXXXXXXXXX  ",
    ]
    img = Image.new("RGBA", (14, 10), (0, 0, 0, 0))
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == 'X':
                img.putpixel((x, y), (*color, 255))
            elif ch == '.':
                img.putpixel((x, y), (255, 255, 255, 255))
    return img.resize((128, 91), Image.Resampling.NEAREST)

img_play = draw_play().resize((32, 32), Image.Resampling.LANCZOS)
img_play.save(os.path.join(ICONS_DIR, "play.png"))
print("Saved play.png successfully!")
