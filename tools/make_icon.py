"""Draw the SPFL Manager app icon (pixel art) and export it for every platform.

    .venv/bin/python tools/make_icon.py

Writes packaging/icon.png (1024px), icon.icns (macOS), icon.ico (Windows) and
src/spfl_manager/assets/icon.png (the in-game window icon). Needs Pillow,
which is in requirements-dev.txt.
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
N = 32  # drawn at 32x32, then scaled up with hard pixel edges

BORDER = (120, 105, 196)  # C64 light blue
SALTIRE_BLUE = (0, 94, 184)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
SHADOW = (40, 40, 90)


def draw() -> Image.Image:
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded tile with a light-blue C64 border
    d.rounded_rectangle((0, 0, N - 1, N - 1), radius=6, fill=BORDER)
    d.rounded_rectangle((2, 2, N - 3, N - 3), radius=5, fill=SALTIRE_BLUE)
    # the saltire, clipped to the inside of the tile
    flag = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    fd = ImageDraw.Draw(flag)
    for off in (-1, 0, 1):
        fd.line((2 + off, 2, N - 3 + off, N - 3), fill=WHITE)
        fd.line((N - 3 + off, 2, 2 + off, N - 3), fill=WHITE)
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).rounded_rectangle((2, 2, N - 3, N - 3), radius=5, fill=255)
    img.paste(flag, (0, 0), Image.composite(flag.getchannel("A"), mask, mask))
    d = ImageDraw.Draw(img)
    # football with a drop shadow: a black centre pentagon with seams running out to the edge
    cx, cy, r = 16, 16, 9
    d.ellipse((cx - r + 1, cy - r + 2, cx + r + 1, cy + r + 2), fill=SHADOW)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=WHITE, outline=BLACK)
    pent = [(16, 12), (19, 14), (18, 18), (14, 18), (13, 14)]
    d.polygon(pent, fill=BLACK)
    for (x, y), (ex, ey) in zip(pent, [(16, 7), (24, 13), (21, 23), (11, 23), (8, 13)]):
        d.line(((x, y), (ex, ey)), fill=BLACK)
    return img


def main():
    icon = draw()
    big = icon.resize((1024, 1024), Image.NEAREST)
    pack = ROOT / "packaging"
    pack.mkdir(exist_ok=True)
    big.save(pack / "icon.png")
    big.save(pack / "icon.icns")
    big.save(pack / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icon.resize((64, 64), Image.NEAREST).save(ROOT / "src" / "spfl_manager" / "assets" / "icon.png")
    print("icons written to", pack)


if __name__ == "__main__":
    main()
