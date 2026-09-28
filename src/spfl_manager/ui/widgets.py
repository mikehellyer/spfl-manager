"""Reusable keyboard + mouse widgets: numbered menus and scrolling tables."""

from __future__ import annotations

import pygame

from . import theme as T


class Menu:
    """A numbered FM2-style menu. Items are (label, callback) or (label, callback, enabled)."""

    def __init__(self, items, x, y, w=260, line_h=18, numbered=True, sound=None):
        self.items = [list(i) + [True] * (3 - len(i)) for i in items]
        self.x, self.y, self.w, self.line_h = x, y, w, line_h
        self.numbered = numbered
        self.index = 0
        self.sound = sound
        self._skip_disabled(1)

    def _skip_disabled(self, step):
        for _ in range(len(self.items)):
            if self.items[self.index][2]:
                return
            self.index = (self.index + step) % len(self.items)

    def _row_at(self, pos):
        x, y = pos
        if self.x <= x <= self.x + self.w:
            i = (y - self.y) // self.line_h
            if 0 <= i < len(self.items):
                return i
        return None

    def activate(self, i):
        if self.items[i][2]:
            if self.sound:
                self.sound.play("select")
            self.items[i][1]()

    def handle(self, ev) -> bool:
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_UP, pygame.K_w):
                self.index = (self.index - 1) % len(self.items)
                self._skip_disabled(-1)
                self._blip()
                return True
            if ev.key in (pygame.K_DOWN, pygame.K_s):
                self.index = (self.index + 1) % len(self.items)
                self._skip_disabled(1)
                self._blip()
                return True
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.activate(self.index)
                return True
            if self.numbered and ev.unicode.isdigit():
                i = int(ev.unicode) - 1 if ev.unicode != "0" else 9
                if 0 <= i < len(self.items):
                    self.index = i
                    self.activate(i)
                    return True
        elif ev.type == pygame.MOUSEMOTION:
            i = self._row_at(ev.pos)
            if i is not None and self.items[i][2] and i != self.index:
                self.index = i
                self._blip()
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            i = self._row_at(ev.pos)
            if i is not None:
                self.index = i
                self.activate(i)
                return True
        return False

    def _blip(self):
        if self.sound:
            self.sound.play("blip")

    def draw(self, surf):
        for i, (label, _, enabled) in enumerate(self.items):
            y = self.y + i * self.line_h
            sel = i == self.index
            if sel:
                pygame.draw.rect(surf, T.HILITE, (self.x, y, self.w, self.line_h - 2))
            color = T.BLACK if sel else (T.TEXT if enabled else T.GREY)
            prefix = f"{(i + 1) % 10}. " if self.numbered and i < 10 else ""
            T.text(surf, prefix + label, (self.x + 6, y + 1), color)


class Table:
    """Scrolling table with a cursor. rows: list of (cells, colour, payload)."""

    def __init__(self, columns, x, y, w, visible=14, line_h=15, on_activate=None, sound=None):
        self.columns = columns  # [(title, x_offset, align)]  align: "l" or "r"
        self.x, self.y, self.w = x, y, w
        self.visible, self.line_h = visible, line_h
        self.rows = []
        self.index = 0
        self.top = 0
        self.on_activate = on_activate
        self.sound = sound
        self.marked: set = set()

    def set_rows(self, rows):
        self.rows = rows
        self.index = min(self.index, max(0, len(rows) - 1))
        self._scroll()

    @property
    def current(self):
        return self.rows[self.index][2] if self.rows else None

    def _scroll(self):
        if self.index < self.top:
            self.top = self.index
        if self.index >= self.top + self.visible:
            self.top = self.index - self.visible + 1

    def _row_at(self, pos):
        x, y = pos
        if self.x <= x <= self.x + self.w:
            i = (y - self.y - self.line_h) // self.line_h
            if 0 <= i < self.visible and self.top + i < len(self.rows):
                return self.top + i
        return None

    def handle(self, ev) -> bool:
        if not self.rows:
            return False
        if ev.type == pygame.KEYDOWN:
            step = {pygame.K_UP: -1, pygame.K_DOWN: 1, pygame.K_PAGEUP: -self.visible, pygame.K_PAGEDOWN: self.visible}
            if ev.key in step:
                self.index = max(0, min(len(self.rows) - 1, self.index + step[ev.key]))
                self._scroll()
                if self.sound:
                    self.sound.play("blip")
                return True
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) and self.on_activate:
                self.on_activate(self.current)
                return True
        elif ev.type == pygame.MOUSEWHEEL:
            self.top = max(0, min(max(0, len(self.rows) - self.visible), self.top - ev.y))
            return True
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            i = self._row_at(ev.pos)
            if i is not None:
                if i == self.index and self.on_activate:
                    self.on_activate(self.current)
                self.index = i
                return True
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
            i = self._row_at(ev.pos)
            if i is not None and self.on_activate:
                self.index = i
                self.on_activate(self.current)
                return True
        return False

    def draw(self, surf):
        for title, off, align in self.columns:
            T.text(surf, title, (self.x + off, self.y), T.TITLE, right=align == "r")
        pygame.draw.line(surf, T.FG, (self.x, self.y + self.line_h - 2), (self.x + self.w, self.y + self.line_h - 2))
        for vi in range(self.visible):
            i = self.top + vi
            if i >= len(self.rows):
                break
            cells, color, _ = self.rows[i]
            y = self.y + (vi + 1) * self.line_h
            if i == self.index:
                pygame.draw.rect(surf, T.HILITE, (self.x - 3, y - 1, self.w + 6, self.line_h))
                color = T.BLACK
            for (title, off, align), cell in zip(self.columns, cells):
                T.text(surf, cell, (self.x + off, y), color, right=align == "r")
        if len(self.rows) > self.visible:
            h = self.visible * self.line_h
            bar_h = max(8, h * self.visible // len(self.rows))
            by = self.y + self.line_h + (h - bar_h) * self.top // max(1, len(self.rows) - self.visible)
            pygame.draw.rect(surf, T.DARK_GREY, (self.x + self.w + 6, self.y + self.line_h, 4, h))
            pygame.draw.rect(surf, T.FG, (self.x + self.w + 6, by, 4, bar_h))


class TextInput:
    def __init__(self, x, y, w, text="", max_len=20):
        self.x, self.y, self.w = x, y, w
        self.value = text
        self.max_len = max_len
        self.t = 0.0

    def handle(self, ev) -> bool:
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
                return True
            if ev.unicode and ev.unicode.isprintable() and len(self.value) < self.max_len:
                if ev.key not in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.value += ev.unicode
                    return True
        return False

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        pygame.draw.rect(surf, T.BLACK, (self.x, self.y, self.w, 20))
        pygame.draw.rect(surf, T.FG, (self.x, self.y, self.w, 20), 1)
        w = T.text(surf, self.value, (self.x + 6, self.y + 3), T.TEXT)
        if int(self.t * 2) % 2 == 0:
            pygame.draw.rect(surf, T.LIGHT_BLUE, (self.x + 7 + w, self.y + 4, 8, 13))
