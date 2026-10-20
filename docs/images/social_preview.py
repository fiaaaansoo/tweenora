import sys
from PIL import Image, ImageDraw, ImageFont

root = sys.argv[1]
W, H = 1280, 640
img = Image.new("RGB", (W, H), "#0f2b2a")
d = ImageDraw.Draw(img)
for y in range(H):
    t = y / H
    c = (int(15 + 10 * t), int(43 + 20 * t), int(42 + 18 * t))
    d.line([(0, y), (W, y)], fill=c)

font_dir = "C:/Windows/Fonts/"
title = ImageFont.truetype(font_dir + "segoeuib.ttf", 112)
tag = ImageFont.truetype(font_dir + "segoeui.ttf", 32)
small = ImageFont.truetype(font_dir + "segoeuib.ttf", 30)

d.text((80, 150), "Tweenora", font=title, fill="#f4f1ea")
d.text((84, 292), "Open source vector animation runtime", font=tag, fill="#cfe5e0")
d.text((84, 340), "Interactive state machines in the browser", font=tag, fill="#9fc7bf")
d.rounded_rectangle([80, 460, 500, 520], radius=30, outline="#4fb3a5", width=3)
d.text((112, 468), "MIT  ·  WebGL2  ·  WASM", font=small, fill="#4fb3a5")

tiles = [
    ("bouncing-ball-048.png", (740, 100)),
    ("spinning-square-030.png", (990, 100)),
    ("button-actif.png", (740, 350)),
    ("tinted-shape-changed.png", (990, 350)),
]
size = 220
for name, (x, y) in tiles:
    tile = Image.open(root + "/docs/examples/renders/" + name).convert("RGBA")
    tile.thumbnail((size, size))
    bg = Image.new("RGBA", (size, size), "#f4f1ea")
    bg.paste(tile, ((size - tile.width) // 2, (size - tile.height) // 2), tile)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], radius=24, fill=255)
    img.paste(bg.convert("RGB"), (x, y), mask)

img.save(root + "/docs/images/social-preview.png", optimize=True)
print(img.size)
