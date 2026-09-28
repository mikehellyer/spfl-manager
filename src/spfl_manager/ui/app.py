"""Main application: window, scaling, scene stack and the frame loop."""

from __future__ import annotations

from pathlib import Path

import pygame

from .. import APP_NAME, __version__, updater
from . import theme as T
from .sound import SoundBank


class Scene:
    def __init__(self, app: App):
        self.app = app

    def handle(self, ev):
        pass

    def update(self, dt: float):
        pass

    def draw(self, surf: pygame.Surface):
        pass

    def on_enter(self):
        """Called whenever the scene becomes the top of the stack again."""


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(f"{APP_NAME} v{__version__}")
        try:
            pygame.display.set_icon(
                pygame.image.load(str(Path(__file__).resolve().parents[1] / "assets" / "icon.png"))
            )
        except (pygame.error, FileNotFoundError):
            pass
        self.window = pygame.display.set_mode((T.CANVAS_W * 2, T.CANVAS_H * 2), pygame.RESIZABLE)
        self.canvas = pygame.Surface((T.CANVAS_W, T.CANVAS_H))
        self.clock = pygame.time.Clock()
        self.sound = SoundBank()
        self.scenes: list[Scene] = []
        self.running = True
        self.game = None
        self.update_info = None
        updater.check_async(self._on_update_info)

    def _on_update_info(self, info):
        self.update_info = info

    # scene stack -----------------------------------------------------
    @property
    def scene(self) -> Scene:
        return self.scenes[-1]

    def push(self, scene: Scene):
        self.scenes.append(scene)
        scene.on_enter()

    def pop(self):
        self.scenes.pop()
        if self.scenes:
            self.scene.on_enter()

    def replace(self, scene: Scene):
        if self.scenes:
            self.scenes.pop()
        self.push(scene)

    def reset(self, scene: Scene):
        self.scenes = []
        self.push(scene)

    # coordinates -------------------------------------------------------
    def _viewport(self):
        ww, wh = self.window.get_size()
        scale = min(ww / T.CANVAS_W, wh / T.CANVAS_H)
        w, h = int(T.CANVAS_W * scale), int(T.CANVAS_H * scale)
        return (ww - w) // 2, (wh - h) // 2, w, h, scale

    def _to_canvas(self, pos):
        x0, y0, _, _, scale = self._viewport()
        return int((pos[0] - x0) / scale), int((pos[1] - y0) / scale)

    # loop ------------------------------------------------------------------
    def run(self, first_scene: Scene):
        self.push(first_scene)
        while self.running and self.scenes:
            dt = min(0.05, self.clock.tick(60) / 1000)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                elif ev.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    self.scene.handle(
                        pygame.event.Event(ev.type, {**ev.dict, "pos": self._to_canvas(ev.pos)})
                    )
                else:
                    self.scene.handle(ev)
                if not self.scenes:
                    break
            if not self.scenes:
                break
            self.scene.update(dt)
            self.scene.draw(self.canvas)
            x0, y0, w, h, _ = self._viewport()
            self.window.fill(T.BLACK)
            self.window.blit(pygame.transform.scale(self.canvas, (w, h)), (x0, y0))
            pygame.display.flip()
        pygame.quit()
