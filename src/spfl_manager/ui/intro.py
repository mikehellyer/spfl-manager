"""Intro: a fake C64 boot/load sequence, then a demo-scene style title screen."""

from __future__ import annotations

import math
import random

import pygame

from .. import __version__
from ..core.game import Game, save_path
from . import theme as T
from .app import Scene
from .widgets import Menu

BOOT_LINES = [
    "",
    "    **** COMMODORE 64 BASIC V2 ****",
    "",
    " 64K RAM SYSTEM  38911 BASIC BYTES FREE",
    "",
    "READY.",
]


class BootScene(Scene):
    """READY. LOAD"SPFL MANAGER",8,1 ... with flashing loading stripes."""

    CMD = 'LOAD"SPFL MANAGER",8,1'

    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        self.rng = random.Random()

    def handle(self, ev):
        if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.replace(TitleScene(self.app))

    def update(self, dt):
        self.t += dt
        if self.t > 6.2:
            self.app.replace(TitleScene(self.app))

    def draw(self, surf):
        t = self.t
        loading = 3.0 < t < 6.0
        if loading:
            # classic tape/disk loading stripes in the border
            surf.fill(T.BLACK)
            y = 0
            while y < T.CANVAS_H:
                h = self.rng.randint(2, 9)
                pygame.draw.rect(surf, self.rng.choice(T.PALETTE), (0, y, T.CANVAS_W, h))
                y += h
            pygame.draw.rect(surf, T.BLUE, (32, 28, T.CANVAS_W - 64, T.CANVAS_H - 56))
        else:
            T.frame(surf, T.LIGHT_BLUE, T.BLUE)
            pygame.draw.rect(surf, T.LIGHT_BLUE, (0, 0, T.CANVAS_W, 28))
            pygame.draw.rect(surf, T.LIGHT_BLUE, (0, T.CANVAS_H - 28, T.CANVAS_W, 28))
            pygame.draw.rect(surf, T.LIGHT_BLUE, (0, 0, 32, T.CANVAS_H))
            pygame.draw.rect(surf, T.LIGHT_BLUE, (T.CANVAS_W - 32, 0, 32, T.CANVAS_H))
        lines = list(BOOT_LINES)
        typed = int(max(0, t - 1.0) * 18)
        if t > 1.0:
            lines.append(self.CMD[:typed])
        if t > 2.4:
            lines += ["", "SEARCHING FOR SPFL MANAGER"]
        if t > 3.0:
            lines += ["LOADING"]
        if t > 5.6:
            lines += ["READY.", "RUN"]
        for i, line in enumerate(lines):
            T.text(surf, line, (40, 34 + i * 14), T.LIGHT_BLUE)
        # blinking cursor
        if int(t * 2.5) % 2 == 0:
            cy = 34 + len(lines) * 14 - (14 if t > 1.0 and typed < len(self.CMD) + 4 else 0)
            cx = 40 + (T.font().size(lines[-1])[0] + 2 if t > 1.0 and typed < len(self.CMD) + 4 else 0)
            pygame.draw.rect(surf, T.LIGHT_BLUE, (cx, cy, 8, 13))


SCROLL_TEXT = (
    "*** WELCOME TO SPFL MANAGER ***   A MODERN TRIBUTE TO THE CLASSIC C64 FOOTBALL MANAGER 2 ... "
    "TAKE CHARGE OF ANY CLUB FROM THE PREMIERSHIP RIGHT DOWN TO LEAGUE TWO ... "
    "PICK YOUR TEAM, WHEEL AND DEAL IN THE TRANSFER MARKET, KEEP THE BANK MANAGER HAPPY "
    "AND WATCH THE HIGHLIGHTS AS YOUR LADS CHASE GLORY IN THE LEAGUE AND THE SCOTTISH CUP ... "
    "CAN YOU TAKE A WEE CLUB ALL THE WAY TO THE TOP?   ...   PRESS SPACE OR CLICK TO KICK OFF   ...   "
)

RASTER_COLOURS = [
    [T.BLUE, T.LIGHT_BLUE, T.CYAN, T.WHITE, T.CYAN, T.LIGHT_BLUE, T.BLUE],
    [T.BROWN, T.ORANGE, T.YELLOW, T.WHITE, T.YELLOW, T.ORANGE, T.BROWN],
    [T.RED, T.LIGHT_RED, T.PURPLE, T.WHITE, T.PURPLE, T.LIGHT_RED, T.RED],
    [T.DARK_GREY, T.GREEN, T.LIGHT_GREEN, T.WHITE, T.LIGHT_GREEN, T.GREEN, T.DARK_GREY],
]
TITLE_CYCLE = [T.WHITE, T.YELLOW, T.LIGHT_GREEN, T.CYAN, T.LIGHT_BLUE, T.PURPLE, T.LIGHT_RED, T.ORANGE]


def _letter_images(word, scale, size=16):
    imgs = []
    for ch in word:
        base = T.font(size, True).render(ch, False, T.WHITE)
        imgs.append(pygame.transform.scale(base, (base.get_width() * scale, base.get_height() * scale)))
    return imgs


_tint_cache: dict = {}


def _tint(img, color):
    key = (id(img), color)
    if key not in _tint_cache:
        mask = pygame.mask.from_surface(img)
        _tint_cache[key] = mask.to_surface(setcolor=color, unsetcolor=(0, 0, 0, 0))
    return _tint_cache[key]


class TitleScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        self.show_menu = False
        self.title1 = _letter_images("SPFL", 5)
        self.title2 = _letter_images("MANAGER", 3)
        self.scroll_imgs = {}
        self.flag = self._make_flag()
        self.stars = [(random.randint(0, T.CANVAS_W), random.randint(0, T.CANVAS_H), random.choice([1, 2, 3])) for _ in range(70)]
        has_save = save_path().exists()
        self.menu = Menu(
            [
                ("New Game", self.new_game),
                ("Continue Saved Game", self.load_game, has_save),
                ("Squad Editor", self.editor),
                ("Quit", self.quit),
            ],
            T.CANVAS_W // 2 - 110,
            238,
            w=220,
            sound=app.sound,
        )
        self.message = ""

    def on_enter(self):
        self.app.sound.play("tune", loops=-1)

    def _make_flag(self):
        w, h = 60, 40
        s = pygame.Surface((w, h))
        s.fill((0, 94, 184))
        for off in range(-3, 4):
            pygame.draw.line(s, T.WHITE, (0, off), (w, h + off), 1)
            pygame.draw.line(s, T.WHITE, (w, off), (0, h + off), 1)
        return s

    def new_game(self):
        from .screens import NewGameScene

        self.app.sound.stop("tune")
        self.app.push(NewGameScene(self.app))

    def editor(self):
        from .editor import open_editor

        open_editor(self.app)

    def load_game(self):
        from .hub import HubScene

        try:
            self.app.game = Game.load(save_path())
        except Exception as exc:  # corrupt or old save
            self.message = f"Can't load: {exc}"[:78]
            return
        self.app.sound.stop("tune")
        self.app.reset(HubScene(self.app))

    def quit(self):
        self.app.running = False

    def handle(self, ev):
        if not self.show_menu:
            if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                if getattr(ev, "key", None) == pygame.K_ESCAPE:
                    self.quit()
                    return
                self.show_menu = True
                self.app.sound.play("select")
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.show_menu = False
            return
        self.menu.handle(ev)

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        t = self.t
        surf.fill(T.BLACK)

        # starfield
        for i, (x, y, sp) in enumerate(self.stars):
            xx = (x - t * 20 * sp) % T.CANVAS_W
            surf.set_at((int(xx), y), [T.DARK_GREY, T.GREY, T.WHITE][sp - 1])

        # rasterbars
        for i, cols in enumerate(RASTER_COLOURS):
            cy = 110 + math.sin(t * 1.7 + i * 0.9) * 70
            for j, c in enumerate(cols):
                pygame.draw.rect(surf, c, (0, int(cy) + j * 3, T.CANVAS_W, 3))

        # big bouncing title
        total = sum(img.get_width() for img in self.title1) + 8 * (len(self.title1) - 1)
        x = T.CANVAS_W // 2 - total // 2
        for i, img in enumerate(self.title1):
            y = 26 + math.sin(t * 3 + i * 0.7) * 6
            col = TITLE_CYCLE[int(t * 8 + i) % len(TITLE_CYCLE)]
            surf.blit(_tint(img, T.BLACK), (x + 4, y + 4))
            surf.blit(_tint(img, col), (x, y))
            x += img.get_width() + 8
        total = sum(img.get_width() for img in self.title2) + 4 * (len(self.title2) - 1)
        x = T.CANVAS_W // 2 - total // 2
        for i, img in enumerate(self.title2):
            y = 118 + math.sin(t * 3 + i * 0.5 + 2) * 3
            surf.blit(_tint(img, T.BLACK), (x + 3, y + 3))
            surf.blit(_tint(img, T.WHITE), (x, y))
            x += img.get_width() + 4

        T.text(surf, "SCOTTISH FOOTBALL  -  PREMIERSHIP TO LEAGUE TWO", (T.CANVAS_W // 2, 186), T.YELLOW, center=True)

        # waving saltire
        fx, fy = 36, 200
        pygame.draw.rect(surf, T.LIGHT_GREY, (fx - 3, fy - 4, 3, 80))
        for col in range(self.flag.get_width()):
            dy = math.sin(t * 5 - col * 0.18) * (col * 0.08)
            surf.blit(self.flag, (fx + col, fy + dy), (col, 0, 1, self.flag.get_height()))

        # bouncing ball with shadow
        bx = T.CANVAS_W - 70 + math.sin(t * 1.3) * 22
        by = 270 - abs(math.sin(t * 3.2)) * 60
        pygame.draw.ellipse(surf, T.DARK_GREY, (bx - 7, 276, 14, 4))
        pygame.draw.circle(surf, T.WHITE, (int(bx), int(by)), 7)
        pygame.draw.circle(surf, T.BLACK, (int(bx), int(by)), 7, 1)
        pygame.draw.circle(surf, T.BLACK, (int(bx + math.sin(t * 8) * 3), int(by)), 2)

        if self.show_menu:
            pygame.draw.rect(surf, T.BLUE, (T.CANVAS_W // 2 - 124, 228, 248, 86))
            pygame.draw.rect(surf, T.LIGHT_BLUE, (T.CANVAS_W // 2 - 124, 228, 248, 86), 2)
            self.menu.draw(surf)
            if self.message:
                T.text(surf, self.message, (T.CANVAS_W // 2, 316), T.LIGHT_RED, center=True, size=11)
        elif int(t * 1.5) % 2 == 0:
            T.big_text(surf, "PRESS SPACE", (T.CANVAS_W // 2, 240), T.WHITE, scale=2, center=True, shadow=T.BLUE)

        # sine scroller
        self._draw_scroller(surf, t)
        T.text(surf, f"v{__version__}", (T.CANVAS_W - 6, 4), T.DARK_GREY, size=10, right=True)

    def _draw_scroller(self, surf, t):
        char_w = 16
        offset = t * 90
        start = int(offset // char_w)
        base_y = 322
        for i in range(T.CANVAS_W // char_w + 2):
            ch = SCROLL_TEXT[(start + i) % len(SCROLL_TEXT)]
            if ch not in self.scroll_imgs:
                img = T.font(13, True).render(ch, False, T.WHITE)
                self.scroll_imgs[ch] = pygame.transform.scale(img, (img.get_width() * 2, img.get_height() * 2))
            x = i * char_w - offset % char_w
            y = base_y + math.sin(t * 4 + x * 0.03) * 8
            col = TITLE_CYCLE[int(x / 40 + t * 4) % len(TITLE_CYCLE)]
            surf.blit(_tint(self.scroll_imgs[ch], col), (x, y))
