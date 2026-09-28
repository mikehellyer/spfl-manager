"""C64 palette, fonts and small drawing helpers.

Everything is drawn onto a low-resolution canvas and scaled up with
nearest-neighbour filtering, which gives the chunky 8-bit look.
"""

from __future__ import annotations

import pygame

CANVAS_W, CANVAS_H = 640, 360
BORDER = 10

# The 16-colour C64 palette (Pepto)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (136, 57, 50)
CYAN = (103, 182, 189)
PURPLE = (139, 63, 150)
GREEN = (85, 160, 73)
BLUE = (64, 49, 141)
YELLOW = (191, 206, 114)
ORANGE = (139, 84, 41)
BROWN = (87, 66, 0)
LIGHT_RED = (184, 105, 98)
DARK_GREY = (80, 80, 80)
GREY = (120, 120, 120)
LIGHT_GREEN = (148, 224, 137)
LIGHT_BLUE = (120, 105, 196)
LIGHT_GREY = (159, 159, 159)

PALETTE = [
    BLACK, WHITE, RED, CYAN, PURPLE, GREEN, BLUE, YELLOW,
    ORANGE, BROWN, LIGHT_RED, DARK_GREY, GREY, LIGHT_GREEN, LIGHT_BLUE, LIGHT_GREY,
]

BG = BLUE
FG = LIGHT_BLUE
TEXT = WHITE
HILITE = CYAN
TITLE = YELLOW

_MONO = "menlo,monaco,dejavusansmono,ubuntumono,consolas,couriernew,courier"
_fonts: dict = {}


def font(size: int = 13, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont(_MONO, size, bold=bold)
    return _fonts[key]


def text(surf, s, pos, color=TEXT, size=13, bold=False, center=False, right=False, shadow=None):
    img = font(size, bold).render(str(s), False, color)
    x, y = pos
    if center:
        x -= img.get_width() // 2
    elif right:
        x -= img.get_width()
    if shadow:
        surf.blit(font(size, bold).render(str(s), False, shadow), (x + 1, y + 1))
    surf.blit(img, (x, y))
    return img.get_width()


def big_text(surf, s, pos, color=TEXT, scale=2, size=13, center=False, shadow=None):
    """Blocky text: render small then scale up with no smoothing."""
    img = font(size, True).render(str(s), False, color)
    img = pygame.transform.scale(img, (img.get_width() * scale, img.get_height() * scale))
    x, y = pos
    if center:
        x -= img.get_width() // 2
    if shadow:
        sh = font(size, True).render(str(s), False, shadow)
        sh = pygame.transform.scale(sh, (sh.get_width() * scale, sh.get_height() * scale))
        surf.blit(sh, (x + scale, y + scale))
    surf.blit(img, (x, y))
    return img.get_width()


def frame(surf, border_color=FG, bg=BG):
    surf.fill(border_color)
    pygame.draw.rect(surf, bg, (BORDER, BORDER, CANVAS_W - 2 * BORDER, CANVAS_H - 2 * BORDER))


def header(surf, title, subtitle="", color=TITLE):
    pygame.draw.rect(surf, BLACK, (BORDER, BORDER, CANVAS_W - 2 * BORDER, 22))
    text(surf, title, (BORDER + 8, BORDER + 4), color, bold=True)
    if subtitle:
        text(surf, subtitle, (CANVAS_W - BORDER - 8, BORDER + 4), LIGHT_GREY, right=True)


def footer(surf, hint):
    y = CANVAS_H - BORDER - 16
    pygame.draw.rect(surf, BLACK, (BORDER, y, CANVAS_W - 2 * BORDER, 16))
    text(surf, hint, (BORDER + 8, y + 2), LIGHT_GREY, size=11)


def bar(surf, x, y, w, h, value, maximum=100, color=LIGHT_GREEN, back=DARK_GREY):
    pygame.draw.rect(surf, back, (x, y, w, h))
    fill = int(w * max(0, min(1, value / maximum)))
    pygame.draw.rect(surf, color, (x, y, fill, h))


def draw_shirt(surf, rect, kit):
    """Fill a shirt rectangle in the club colours, with stripes or hoops."""
    shirt, _, pattern, shirt2 = kit
    x, y, w, h = (int(v) for v in rect)
    pygame.draw.rect(surf, shirt, (x, y, w, h))
    band = max(1, w // 5) if pattern == "stripes" else max(1, h // 5)
    if pattern == "stripes":
        for sx in range(x + band, x + w - 1, band * 2):
            pygame.draw.rect(surf, shirt2, (sx, y, band, h))
    elif pattern == "hoops":
        for sy in range(y + band, y + h - 1, band * 2):
            pygame.draw.rect(surf, shirt2, (x, sy, w, band))


def kit_swatch(surf, x, y, kit, w=10, h=12):
    shorts = kit[1]
    draw_shirt(surf, (x, y, w, h * 2 // 3), kit)
    pygame.draw.rect(surf, shorts, (x + 1, y + h * 2 // 3, w - 2, h // 3))
    pygame.draw.rect(surf, BLACK, (x, y, w, h), 1)


def money(n: int) -> str:
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1_000_000:
        return f"{sign}£{n / 1_000_000:.2f}M"
    if n >= 10_000:
        return f"{sign}£{n // 1000}K"
    return f"{sign}£{n:,}"


def wrap(s: str, width: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def color_distance(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _kit_colour(kit):
    shirt, _, pattern, shirt2 = kit
    if not pattern:
        return shirt
    return tuple((a + b) // 2 for a, b in zip(shirt, shirt2))


def away_kit(home, away):
    """Swap the away side into a change strip when the kits clash."""
    hc, ac = _kit_colour(home), _kit_colour(away)
    if color_distance(hc, ac) > 130 and color_distance(home[0], away[0]) > 90:
        return away
    if color_distance(hc, (240, 240, 240)) > 130:
        return ((240, 240, 240), (40, 40, 40), "", (240, 240, 240))
    return ((220, 40, 40), (240, 240, 240), "", (220, 40, 40))
