"""The main management menu shown between matches."""

from __future__ import annotations

import pygame

from ..core import data
from ..core.game import Game, save_path
from . import theme as T
from .app import Scene
from .screens import (
    TOP,
    FinanceScene,
    FixturesScene,
    L,
    MarketScene,
    MessageScene,
    NewsScene,
    PreMatchScene,
    SquadScene,
    TableScene,
    open_update,
    ordinal,
)
from .widgets import Menu


class HubScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.build_menu()

    def build_menu(self):
        app = self.app
        items = [
            ("Play Next Match", lambda: app.push(PreMatchScene(app))),
            ("Squad & Pick Team", lambda: app.push(SquadScene(app))),
            ("League Tables", lambda: app.push(TableScene(app))),
            ("Fixtures & Results", lambda: app.push(FixturesScene(app))),
            ("Transfer Market", lambda: app.push(MarketScene(app))),
            ("Finances & Bank", lambda: app.push(FinanceScene(app))),
            ("News", lambda: app.push(NewsScene(app))),
            ("Squad Editor", self.editor),
            ("Save Game", self.save),
            ("Quit to Title", self.quit),
        ]
        if app.update_info:
            items.append(
                (
                    f"U. UPDATE TO v{app.update_info['version']}",
                    lambda: open_update(app),
                    True,
                    "alert",
                )
            )
        self.menu = Menu(items, T.CANVAS_W - 250, TOP + 20, w=228, line_h=19, sound=app.sound)
        self._had_update = bool(app.update_info)

    @property
    def g(self) -> Game:
        return self.app.game

    def editor(self):
        from .editor import EditorScene, SaveBackend

        self.app.push(EditorScene(self.app, SaveBackend(self.app)))

    def save(self):
        try:
            self.g.save(save_path())
            self.app.push(MessageScene(self.app, "GAME SAVED", [f"Saved to {save_path()}"]))
        except OSError as exc:
            self.app.push(MessageScene(self.app, "SAVE FAILED", [str(exc)]))

    def quit(self):
        from .intro import TitleScene

        self.g.save(save_path())
        self.app.reset(TitleScene(self.app))

    def on_enter(self):
        if self.app.update_info and not self._had_update:
            self.build_menu()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.quit()
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_u and self.app.update_info:
            open_update(self.app)
            return
        self.menu.handle(ev)

    def update(self, dt):
        if self.app.update_info and not self._had_update:
            self.build_menu()

    def draw(self, surf):
        g = self.g
        club = g.club
        T.frame(surf)
        T.header(surf, f"{club.name.upper()}", f"{g.season_label}  -  {g.event_label()}")

        # club panel
        x, y = L, TOP + 8
        T.kit_swatch(surf, x, y + 2, club.kit, 22, 28)
        T.big_text(surf, club.short, (x + 34, y), T.YELLOW, scale=2)
        T.text(surf, f"Manager: {g.manager}", (x + 110, y + 2), T.WHITE)
        T.text(surf, data.DIVISION_FULL[club.division], (x + 110, y + 18), T.LIGHT_GREY)
        y += 44
        row = g.tables[g.club_name]
        pos = g.position()
        stats = [
            ("League position", f"{ordinal(pos)} of {len(g.divisions[club.division])}"),
            ("Played / Points", f"{row['P']} / {row['Pts']}"),
            ("Record W-D-L", f"{row['W']}-{row['D']}-{row['L']}   form {row['form'] or '-'}"),
            ("Bank balance", T.money(g.balance) + (f"  (loan {T.money(g.loan)})" if g.loan else "")),
            ("Weekly wages", T.money(g.wage_bill())),
            ("Scottish Cup", g.cup_status()),
            ("League Cup", g.league_cup_status()),
        ]
        for label, val in stats:
            T.text(surf, label, (x, y), T.LIGHT_GREY)
            col = T.LIGHT_RED if label == "Bank balance" and g.balance < 0 else T.WHITE
            T.text(surf, val, (x + 140, y), col)
            y += 16
        T.text(surf, "Morale", (x, y), T.LIGHT_GREY)
        T.bar(surf, x + 140, y + 3, 150, 8, club.morale, 100, T.YELLOW)
        y += 24

        # next fixture box
        pygame.draw.rect(surf, T.BLACK, (x - 4, y, 340, 50))
        T.text(surf, "NEXT: " + g.event_label().upper(), (x + 4, y + 4), T.CYAN, bold=True)
        fx = g.next_fixture()
        if fx:
            h, a, _ = fx
            venue = "HOME" if h == g.club_name else "AWAY"
            if g.cup_neutral(fx[2]):
                venue = "HAMPDEN"
            opp = a if h == g.club_name else h
            opp_pos = g.position(opp)
            same_div = g.clubs[opp].division == club.division
            extra = (
                f" ({ordinal(opp_pos)})"
                if same_div
                else f" ({data.division_name(g.clubs[opp].division, False)})"
            )
            T.text(surf, f"{venue} v {opp}{extra}", (x + 4, y + 24), T.WHITE)
            if "play-off" in fx[2]:
                T.text(surf, fx[2].split(" (")[0], (x + 4, y + 38), T.YELLOW, size=10)
        else:
            T.text(surf, "No match for your club this week", (x + 4, y + 24), T.LIGHT_GREY)

        # news ticker
        if g.news:
            for i, line in enumerate(T.wrap(g.news[0], 88)[:2]):
                T.text(surf, line, (L, T.CANVAS_H - T.BORDER - 46 + i * 13), T.LIGHT_GREEN, size=11)
        if g.board_warnings:
            T.text(
                surf,
                f"BOARD WARNING {g.board_warnings}/3 - reduce the overdraft!",
                (T.CANVAS_W - 250, self.menu.y + len(self.menu.items) * self.menu.line_h + 4),
                T.LIGHT_RED,
                size=11,
            )
        self.menu.draw(surf)
        T.footer(surf, "Number keys, arrows + RETURN, or mouse.  F11: fullscreen   ESC: save & quit to title")
