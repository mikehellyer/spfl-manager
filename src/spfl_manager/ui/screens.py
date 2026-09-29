"""All the management screens (FM2-style menus)."""

from __future__ import annotations

import webbrowser

import pygame

from ..core import cup as cupmod
from ..core import data
from ..core import league_cup as lcup
from ..core.game import MAX_SQUAD, Game, save_path
from ..core.models import team_strength
from . import theme as T
from .app import Scene
from .widgets import Menu, Table, TextInput

L = T.BORDER + 10  # left margin
TOP = T.BORDER + 30


def is_back(ev) -> bool:
    return (ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE)) or (
        ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3
    )


class MessageScene(Scene):
    """Modal message box. Optional yes/no."""

    def __init__(
        self, app, title, lines, on_yes=None, on_no=None, yes_label="Yes", no_label="No", esc_cancels=False
    ):
        super().__init__(app)
        self.esc_cancels = esc_cancels  # ESC just closes the box instead of meaning "No"
        self.title, self.lines = title, []
        for line in lines:
            self.lines += T.wrap(line, 52) or [""]
        self.on_yes, self.on_no = on_yes, on_no
        self.under = app.scenes[-1] if app.scenes else None
        h = 64 + len(self.lines) * 15 + (40 if on_yes else 0)
        self.rect = pygame.Rect(T.CANVAS_W // 2 - 230, T.CANVAS_H // 2 - h // 2, 460, h)
        self.menu = None
        if on_yes:
            w = max(160, 8 * max(len(yes_label), len(no_label)) + 50)
            self.menu = Menu(
                [(f"{yes_label} (Y)", self._yes), (f"{no_label} (N)", self._no)],
                self.rect.centerx - w // 2,
                self.rect.bottom - 48,
                w=w,
                sound=app.sound,
                numbered=False,
            )

    def _yes(self):
        self.app.pop()
        self.on_yes()

    def _no(self):
        self.app.pop()
        if self.on_no:
            self.on_no()

    def handle(self, ev):
        if self.menu:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE and self.esc_cancels:
                self.app.pop()
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_y:
                self._yes()
            elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_n, pygame.K_ESCAPE):
                self._no()
            else:
                self.menu.handle(ev)
        elif ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.pop()

    def draw(self, surf):
        if self.under:
            self.under.draw(surf)
        r = self.rect
        pygame.draw.rect(surf, T.BLACK, r.move(4, 4))
        pygame.draw.rect(surf, T.BLUE, r)
        pygame.draw.rect(surf, T.YELLOW, r, 2)
        T.text(surf, self.title, (r.centerx, r.y + 10), T.YELLOW, bold=True, center=True)
        for i, line in enumerate(self.lines):
            T.text(surf, line, (r.x + 16, r.y + 34 + i * 15), T.WHITE)
        if self.menu:
            self.menu.draw(surf)
        else:
            T.text(surf, "Press any key", (r.centerx, r.bottom - 20), T.LIGHT_GREY, size=11, center=True)


# --------------------------------------------------------------------------- new game
class NewGameScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.step = 0
        self.input = TextInput(L + 150, 90, 240, "", 20)
        self.division = 3
        self.div_menu = Menu(
            [
                (
                    f"{data.DIVISION_FULL[i]}" + ("  (classic start)" if i == 3 else ""),
                    lambda i=i: self.pick_div(i),
                )
                for i in range(4)
            ],
            L + 150,
            150,
            w=300,
            sound=app.sound,
        )
        self.div_menu.index = 3
        self.club_table = None

    def pick_div(self, i):
        self.division = i
        self.step = 2
        self.club_table = Table(
            [("Club", 26, "l"), ("Ground", 230, "l"), ("Cap", 470, "r"), ("Squad", 530, "l")],
            L,
            TOP + 40,
            570,
            visible=12,
            on_activate=self.pick_club,
            sound=self.app.sound,
        )
        rows = []
        weakest = min(c.rating for c in data.CLUBS[i])
        for c in data.CLUBS[i]:
            stars = "*" * max(1, min(5, (c.rating - weakest) // 3 + 1))
            rows.append(([c.name, c.stadium, f"{c.capacity:,}", stars], T.WHITE, c.name))
        self.club_table.set_rows(rows)

    def pick_club(self, name):
        from .hub import HubScene

        game = Game.new(self.input.value.strip() or "Manager", name)
        self.app.game = game
        game.save(save_path())
        self.app.reset(HubScene(self.app))
        club = game.club
        self.app.push(
            MessageScene(
                self.app,
                f"WELCOME TO {club.name.upper()}",
                [
                    f"{game.manager}, you are the new manager of {club.name}.",
                    f"Home ground: {club.stadium} ({club.capacity:,}).",
                    f"Bank balance: {T.money(game.balance)}. Weekly wages: {T.money(game.wage_bill())}.",
                    "Pick your team, keep the board happy and chase promotion!",
                ],
            )
        )

    def handle(self, ev):
        if self.step == 0:
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.input.value.strip():
                    self.step = 1
                    self.app.sound.play("select")
            elif (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE) or (
                ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3
            ):
                self.app.pop()
            else:
                self.input.handle(ev)
        elif self.step == 1:
            if is_back(ev):
                self.step = 0
            else:
                self.div_menu.handle(ev)
        else:
            if is_back(ev):
                self.step = 1
            else:
                self.club_table.handle(ev)

    def update(self, dt):
        self.input.update(dt)

    def draw(self, surf):
        T.frame(surf)
        T.header(surf, "NEW GAME", ["1. Your name", "2. Choose a division", "3. Choose a club"][self.step])
        if self.step == 0:
            T.big_text(surf, "WHAT IS YOUR NAME?", (T.CANVAS_W // 2, 50), T.YELLOW, center=True)
            T.text(surf, "Manager name:", (L + 30, 93), T.LIGHT_GREY)
            self.input.draw(surf)
            T.text(surf, "Type your name and press RETURN", (T.CANVAS_W // 2, 130), T.LIGHT_BLUE, center=True)
        elif self.step == 1:
            T.big_text(surf, "CHOOSE A DIVISION", (T.CANVAS_W // 2, 50), T.YELLOW, center=True)
            T.text(surf, f"Manager: {self.input.value}", (T.CANVAS_W // 2, 100), T.WHITE, center=True)
            self.div_menu.draw(surf)
            T.text(
                surf,
                "Like the original, starting at the bottom is the real challenge.",
                (T.CANVAS_W // 2, 250),
                T.LIGHT_BLUE,
                center=True,
                size=11,
            )
            T.footer(surf, "UP/DOWN + RETURN or click to choose   ESC back")
        else:
            T.text(surf, data.DIVISION_FULL[self.division], (L, TOP + 10), T.YELLOW, bold=True)
            self.club_table.draw(surf)
            for vi in range(self.club_table.visible):
                i = self.club_table.top + vi
                if i >= len(self.club_table.rows):
                    break
                c = data.CLUBS[self.division][i]
                T.kit_swatch(
                    surf, L + 6, TOP + 40 + (vi + 1) * 15, (c.shirt, c.shorts, c.pattern, c.shirt2), 10, 12
                )
            T.footer(surf, "Double-click or RETURN to take charge   ESC back")


# --------------------------------------------------------------------------- squad
class SquadScene(Scene):
    def __init__(self, app, sell_mode=False):
        super().__init__(app)
        self.g: Game = app.game
        self.table = Table(
            [
                ("", 0, "l"),
                ("Name", 16, "l"),
                ("Pos", 150, "l"),
                ("Skill", 222, "r"),
                ("Fit", 262, "r"),
                ("Age", 296, "r"),
                ("Value", 370, "r"),
                ("Wage", 430, "r"),
                ("Gls", 466, "r"),
                ("Status", 480, "l"),
            ],
            L,
            TOP + 58,
            580,
            visible=14,
            line_h=15,
            on_activate=self.toggle,
            sound=app.sound,
            click_activates=True,  # one left-click picks/drops a player
        )
        self.msg = ""
        self.refresh()

    def on_enter(self):
        self.refresh()

    def refresh(self):
        g = self.g
        sel = set(g.club.selected)
        rows = []
        for p in g.squad(g.club_name):
            status = f"INJ {p.injury}w" if p.injury else ("PICKED" if p.id in sel else "")
            color = T.YELLOW if p.id in sel else (T.LIGHT_RED if p.injury else T.WHITE)
            rows.append(
                (
                    [
                        "*" if p.id in sel else "",
                        p.short_name,
                        p.pos,
                        str(p.skill),
                        f"{p.energy}%",
                        str(p.age),
                        T.money(p.value),
                        T.money(p.wage),
                        str(p.goals),
                        status,
                    ],
                    color,
                    p.id,
                )
            )
        self.table.set_rows(rows)

    def toggle(self, pid):
        self.msg = self.g.toggle_selection(pid)
        self.refresh()

    def auto(self):
        self.g.club.selected = self.g.auto_pick(self.g.club_name)
        self.msg = "Best available 4-4-2 picked."
        self.refresh()

    def sell(self):
        pid = self.table.current
        if pid is None:
            return
        p = self.g.players[pid]
        offer = self.g.sale_offer(pid)
        if offer is None:
            self.msg = "Squad too small to sell anyone."
            return
        buyer, fee = offer

        def accept():
            self.msg = self.g.accept_sale(pid, buyer, fee)
            self.refresh()

        self.app.push(
            MessageScene(
                self.app,
                "TRANSFER OFFER",
                [
                    f"{buyer} offer {T.money(fee)} for {p.name} ({p.pos}, skill {p.skill}).",
                    f"His valuation is {T.money(p.value)}. Accept the offer?",
                ],
                on_yes=accept,
            )
        )

    def handle(self, ev):
        if is_back(ev):  # ESC, Backspace or right-click
            self.app.pop()
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_a:
                self.auto()
                return
            if ev.key == pygame.K_x:
                self.g.club.selected = []
                self.refresh()
                return
            if ev.key == pygame.K_l:
                self.sell()
                return
        self.table.handle(ev)

    def draw(self, surf):
        g = self.g
        T.frame(surf)
        T.header(surf, f"{g.club.name.upper()} - SQUAD", f"{len(g.squad(g.club_name))}/{MAX_SQUAD} players")
        xi = g.selected_players(g.club_name)
        counts = {pos: sum(1 for p in xi if p.pos == pos) for pos in ("GK", "DEF", "MID", "ATT")}
        shape = f"{counts['DEF']}-{counts['MID']}-{counts['ATT']}"
        col = T.LIGHT_GREEN if len(xi) == 11 else T.LIGHT_RED
        T.text(
            surf, f"PICKED {len(xi)}/11   FORMATION {shape}   GK {counts['GK']}", (L, TOP + 2), col, bold=True
        )
        s = team_strength(xi)
        for i, (label, v) in enumerate((("DEF", s.defence), ("MID", s.midfield), ("ATT", s.attack))):
            x = L + i * 190
            T.text(surf, label, (x, TOP + 22), T.LIGHT_GREY)
            T.bar(surf, x + 34, TOP + 25, 130, 8, v, 99, T.LIGHT_GREEN)
            T.text(surf, f"{v:.0f}", (x + 168, TOP + 22), T.WHITE)
        T.text(surf, "Team morale", (L, TOP + 38), T.LIGHT_GREY, size=11)
        T.bar(surf, L + 90, TOP + 41, 100, 6, g.club.morale, 100, T.YELLOW)
        if self.msg:
            T.text(surf, self.msg, (L + 210, TOP + 38), T.LIGHT_RED, size=11)
        self.table.draw(surf)
        T.footer(surf, "Click/RETURN: pick/drop   A: auto-pick   X: clear   L: sell   Right-click/ESC: back")


# --------------------------------------------------------------------------- tables
class TableScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.g: Game = app.game
        self.div = self.g.club.division
        self.table = Table(
            [
                ("Pos", 0, "l"),
                ("Club", 34, "l"),
                ("P", 270, "r"),
                ("W", 300, "r"),
                ("D", 330, "r"),
                ("L", 360, "r"),
                ("F", 395, "r"),
                ("A", 430, "r"),
                ("GD", 470, "r"),
                ("Pts", 510, "r"),
                ("Form", 528, "l"),
            ],
            L,
            TOP + 20,
            580,
            visible=12,
            line_h=17,
            sound=app.sound,
        )
        self.refresh()

    def refresh(self):
        g = self.g
        rows = []
        n = len(g.divisions[self.div])
        for i, (name, r) in enumerate(g.table(self.div)):
            pos = i + 1
            if name == g.club_name:
                color = T.YELLOW
            elif pos == 1 and self.div > 0:
                color = T.LIGHT_GREEN  # automatic promotion
            elif pos == n and self.div < 3:
                color = T.LIGHT_RED  # automatic relegation
            elif self.div > 0 and pos in (2, 3, 4):
                color = T.CYAN  # promotion play-off
            elif (
                (self.div == 0 and pos == 11)
                or (self.div in (1, 2) and pos == 9)
                or (self.div == 3 and pos == n)
            ):
                color = (230, 150, 70)  # relegation play-off
            else:
                color = T.WHITE
            rows.append(
                (
                    [
                        str(i + 1),
                        name,
                        str(r["P"]),
                        str(r["W"]),
                        str(r["D"]),
                        str(r["L"]),
                        str(r["F"]),
                        str(r["A"]),
                        f"{r['F'] - r['A']:+d}",
                        str(r["Pts"]),
                        r["form"],
                    ],
                    color,
                    name,
                )
            )
        self.table.set_rows(rows)

    def handle(self, ev):
        if is_back(ev):
            self.app.pop()
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
            pages = 5 if self.g.league_cup.get("groups") else 4  # 5th page: League Cup groups
            self.div = (self.div + (1 if ev.key == pygame.K_RIGHT else -1)) % pages
            self.table.index = self.table.top = 0
            if self.div < 4:
                self.refresh()
        elif self.div < 4:
            self.table.handle(ev)

    def draw_league_cup_groups(self, surf):
        g = self.g
        st = g.league_cup
        T.header(surf, "LEAGUE CUP - GROUP STAGE", f"{g.season_label}  {g.event_label()}")
        for gi in range(8):
            col, row = gi % 2, gi // 2
            x, y = L + col * 300, TOP + 4 + row * 72
            T.text(surf, f"GROUP {lcup.GROUP_NAMES[gi]}", (x, y), T.YELLOW, size=10, bold=True)
            T.text(surf, "P  Pts", (x + 280, y), T.GREY, size=10, right=True)
            for i, team in enumerate(lcup.standings(st, gi)):
                r = st["tables"][team]
                ty = y + 12 + i * 11
                colr = T.YELLOW if team == g.club_name else (T.LIGHT_GREEN if i == 0 else T.WHITE)
                T.text(surf, cupmod.display_name(team, 26), (x, ty), colr, size=10)
                T.text(surf, f"{r['P']}  {r['Pts']:>3}", (x + 280, ty), colr, size=10, right=True)
        note = "Winners and the 3 best runners-up join the 5 European clubs in the Second Round."
        T.text(surf, note, (L, TOP + 4 + 4 * 72 + 2), T.LIGHT_GREY, size=10)
        T.footer(
            surf, "Win 3 pts, draw goes to penalties: winner 2, loser 1   LEFT/RIGHT: tables   ESC: back"
        )

    def draw(self, surf):
        T.frame(surf)
        if self.div == 4:
            self.draw_league_cup_groups(surf)
            return
        extra = ""
        if self.div == 0:
            extra = "  (split: top 6 / bottom 6)" if self.g.split else "  (splits after 33 games)"
        T.header(
            surf,
            data.DIVISION_FULL[self.div].upper() + extra,
            f"{self.g.season_label}  {self.g.event_label()}",
        )
        self.table.draw(surf)
        if self.div == 0 and self.g.split and self.table.top <= 6:
            ly = TOP + 20 + (7 - self.table.top) * 17 - 2
            pygame.draw.line(surf, T.YELLOW, (L - 4, ly), (L + 584, ly), 1)
            T.text(surf, "SPLIT", (L + 590, ly - 6), T.YELLOW, size=9)
        y = TOP + 20 + 13 * 17 + 6
        T.text(
            surf,
            "Green: promoted  Cyan: promotion play-off  Orange: relegation play-off  Red: relegated",
            (L, y),
            T.LIGHT_GREY,
            size=11,
        )
        T.footer(surf, "LEFT/RIGHT: other divisions and League Cup groups   Right-click/ESC: back")


# --------------------------------------------------------------------------- fixtures
class FixturesScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        g: Game = app.game
        self.g = g
        self.table = Table(
            [("Wk", 0, "l"), ("Home", 40, "l"), ("Score", 300, "r"), ("Away", 320, "l")],
            L,
            TOP + 6,
            580,
            visible=17,
            line_h=15,
            sound=app.sound,
        )
        played = {}
        for r in g.player_results:
            played[(r["home"], r["away"], r["label"])] = r
        rows = []
        current = None
        for rnd, h, a in g.league_fixture_list():
            res = played.get((h, a, f"League Week {rnd + 1}"))
            if res:
                score = f"{res['home_goals']}-{res['away_goals']}"
                me_h = h == g.club_name
                gf, ga = (
                    (res["home_goals"], res["away_goals"]) if me_h else (res["away_goals"], res["home_goals"])
                )
                color = T.LIGHT_GREEN if gf > ga else (T.LIGHT_RED if gf < ga else T.YELLOW)
            else:
                score, color = "v", T.WHITE
                if current is None:
                    current = len(rows)
            rows.append(([str(rnd + 1), h, score, a], color, None))
        for r in g.player_results:
            if not r["label"].startswith("League"):
                score = f"{r['home_goals']}-{r['away_goals']}" + (" p" if r["pens"] else "")
                tag = (
                    "P/O"
                    if r["label"].startswith("Play-offs")
                    else "LC"
                    if r["label"].startswith("League Cup")
                    else "CUP"
                )
                rows.append(([tag, r["home"], score, r["away"]], T.CYAN if tag == "CUP" else T.YELLOW, None))
        self.table.set_rows(rows)
        if current is not None:
            self.table.index = current
            self.table._scroll()

    def handle(self, ev):
        if is_back(ev):
            self.app.pop()
        else:
            self.table.handle(ev)

    def draw(self, surf):
        T.frame(surf)
        T.header(surf, f"{self.g.club.name.upper()} - FIXTURES & RESULTS", self.g.season_label)
        self.table.draw(surf)
        T.footer(surf, "Green: win  Yellow: draw  Red: defeat  Cyan: cup  P/O: play-off   ESC: back")


# --------------------------------------------------------------------------- transfers
class BidScene(Scene):
    def __init__(self, app, pid, asking, parent):
        super().__init__(app)
        self.g: Game = app.game
        self.pid, self.asking, self.parent = pid, asking, parent
        self.amount = asking
        self.step = max(1000, asking // 20 // 1000 * 1000)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.app.pop()
            elif ev.key in (pygame.K_UP, pygame.K_RIGHT, pygame.K_EQUALS, pygame.K_PLUS):
                self.amount += self.step
            elif ev.key in (pygame.K_DOWN, pygame.K_LEFT, pygame.K_MINUS):
                self.amount = max(self.step, self.amount - self.step)
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.submit()
        elif ev.type == pygame.MOUSEWHEEL:
            self.amount = max(self.step, self.amount + self.step * ev.y)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.submit()
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
            self.app.pop()

    def submit(self):
        ok, msg = self.g.bid(self.pid, self.amount)
        self.app.pop()
        self.app.sound.play("select" if ok else "blip")
        self.parent.refresh()
        self.app.push(MessageScene(self.app, "SIGNED!" if ok else "BID REJECTED", [msg]))

    def draw(self, surf):
        self.parent.draw(surf)
        p = self.g.players[self.pid]
        r = pygame.Rect(T.CANVAS_W // 2 - 200, 110, 400, 140)
        pygame.draw.rect(surf, T.BLACK, r.move(4, 4))
        pygame.draw.rect(surf, T.BLUE, r)
        pygame.draw.rect(surf, T.YELLOW, r, 2)
        T.text(surf, "MAKE A BID", (r.centerx, r.y + 8), T.YELLOW, bold=True, center=True)
        T.text(
            surf,
            f"{p.name}  {p.pos}  skill {p.skill}  age {p.age}  ({p.club})",
            (r.centerx, r.y + 30),
            T.WHITE,
            center=True,
        )
        T.text(
            surf,
            f"Asking price {T.money(self.asking)}   You have {T.money(self.g.balance)}",
            (r.centerx, r.y + 48),
            T.LIGHT_GREY,
            center=True,
        )
        T.big_text(surf, f"£{self.amount:,}", (r.centerx, r.y + 70), T.LIGHT_GREEN, center=True)
        T.text(
            surf,
            "UP/DOWN or wheel to change  RETURN/click to bid  ESC cancel",
            (r.centerx, r.bottom - 20),
            T.LIGHT_GREY,
            size=11,
            center=True,
        )


class MarketScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.g: Game = app.game
        self.table = Table(
            [
                ("Name", 0, "l"),
                ("Pos", 130, "l"),
                ("Club", 172, "l"),
                ("Skill", 380, "r"),
                ("Age", 420, "r"),
                ("Asking", 500, "r"),
                ("Wage", 570, "r"),
            ],
            L,
            TOP + 36,
            580,
            visible=8,
            line_h=17,
            on_activate=self.bid,
            sound=app.sound,
        )
        self.refresh()

    def refresh(self):
        rows = []
        for pid, asking in self.g.market:
            p = self.g.players[pid]
            rows.append(
                (
                    [p.short_name, p.pos, p.club, str(p.skill), str(p.age), T.money(asking), T.money(p.wage)],
                    T.WHITE,
                    (pid, asking),
                )
            )
        self.table.set_rows(rows)

    def bid(self, payload):
        if payload:
            self.app.push(BidScene(self.app, payload[0], payload[1], self))

    def handle(self, ev):
        if is_back(ev):
            self.app.pop()
        else:
            self.table.handle(ev)

    def draw(self, surf):
        g = self.g
        T.frame(surf)
        T.header(surf, "TRANSFER MARKET", f"Bank: {T.money(g.balance)}")
        T.text(surf, "Players available this week:", (L, TOP + 6), T.YELLOW)
        if not self.table.rows:
            T.text(surf, "Nobody available - check back next week.", (L, TOP + 60), T.LIGHT_GREY)
        self.table.draw(surf)
        y = TOP + 36 + 10 * 17
        T.text(
            surf,
            f"Squad size {len(g.squad(g.club_name))}/{MAX_SQUAD}.  To sell a player go to the Squad screen and press L.",
            (L, y),
            T.LIGHT_GREY,
            size=11,
        )
        T.text(surf, "The market changes every week.", (L, y + 14), T.LIGHT_GREY, size=11)
        T.footer(surf, "RETURN/double-click: make a bid   Right-click/ESC: back")


# --------------------------------------------------------------------------- finance
class FinanceScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.g: Game = app.game
        self.msg = ""
        self.menu = Menu(
            [
                ("Borrow £25K", lambda: self.act(self.g.borrow, 25_000)),
                ("Borrow £100K", lambda: self.act(self.g.borrow, 100_000)),
                ("Repay £25K", lambda: self.act(self.g.repay, 25_000)),
                ("Repay £100K", lambda: self.act(self.g.repay, 100_000)),
                ("Back", app.pop),
            ],
            T.CANVAS_W - 230,
            TOP + 40,
            w=200,
            sound=app.sound,
        )

    def act(self, fn, amount):
        self.msg = fn(amount)

    def handle(self, ev):
        if is_back(ev):
            self.app.pop()
        else:
            self.menu.handle(ev)

    def draw(self, surf):
        g = self.g
        div = g.club.division
        T.frame(surf)
        T.header(surf, "FINANCES & BANK", g.season_label)
        y = TOP + 10
        rows = [
            ("Bank balance", T.money(g.balance), T.LIGHT_GREEN if g.balance >= 0 else T.LIGHT_RED),
            ("Bank loan", T.money(g.loan), T.WHITE),
            ("Loan limit", T.money(data.LOAN_LIMIT[div]), T.LIGHT_GREY),
            ("Loan interest", f"{data.LOAN_WEEKLY_INTEREST * 100:.1f}% a week", T.LIGHT_GREY),
            ("Overdraft limit", T.money(data.OVERDRAFT_LIMIT[div]), T.LIGHT_GREY),
            ("Weekly wage bill", T.money(g.wage_bill()), T.WHITE),
            ("Ticket price", f"£{data.TICKET_PRICE[div]}", T.WHITE),
        ]
        for label, val, col in rows:
            T.text(surf, label, (L, y), T.LIGHT_GREY)
            T.text(surf, val, (L + 300, y), col, right=True)
            y += 17
        y += 8
        T.text(surf, "LAST WEEK", (L, y), T.YELLOW, bold=True)
        y += 18
        if not g.last_finance:
            T.text(surf, "No matches played yet.", (L, y), T.LIGHT_GREY)
        for k, v in g.last_finance.items():
            if k.startswith("_"):
                continue
            col = T.LIGHT_GREEN if v >= 0 else T.LIGHT_RED
            T.text(surf, k, (L, y), T.WHITE if k != "Net" else T.YELLOW)
            T.text(surf, T.money(v), (L + 300, y), col, right=True)
            y += 15
        if "_crowd" in g.last_finance:
            T.text(surf, f"Crowd: {g.last_finance['_crowd']:,}", (L, y + 4), T.LIGHT_GREY, size=11)
        if g.board_warnings:
            T.text(
                surf,
                f"BOARD WARNINGS: {g.board_warnings}/3",
                (T.CANVAS_W - 230, TOP + 150),
                T.LIGHT_RED,
                bold=True,
            )
        self.menu.draw(surf)
        if self.msg:
            T.text(surf, self.msg, (T.CANVAS_W - 230, TOP + 136), T.YELLOW, size=11)
        T.footer(surf, "Stay inside the overdraft limit or the board will sack you!   Right-click/ESC: back")


class NewsScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.g = app.game
        lines = []
        for item in self.g.news:
            wrapped = T.wrap(item, 74)
            lines += [(w, i == 0) for i, w in enumerate(wrapped)]
        self.table = Table([("Latest news", 0, "l")], L, TOP + 4, 580, visible=18, line_h=15, sound=app.sound)
        self.table.set_rows([([w], T.WHITE if first else T.LIGHT_GREY, None) for w, first in lines])

    def handle(self, ev):
        if is_back(ev):
            self.app.pop()
        else:
            self.table.handle(ev)

    def draw(self, surf):
        T.frame(surf)
        T.header(surf, "NEWS", self.g.event_label())
        self.table.draw(surf)
        T.footer(surf, "Right-click/ESC: back")


# --------------------------------------------------------------------------- match flow
class PreMatchScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.g: Game = app.game
        self.fixture = self.g.next_fixture()
        items = [("Watch the Highlights", self.play)]
        if self.fixture:
            items.append(("Quick Result (no highlights)", lambda: self.play(quick=True)))
        items += [("Pick Team", lambda: app.push(SquadScene(app))), ("Back", app.pop)]
        if not self.fixture:
            items[0] = ("Continue (no game this week)", self.play)
        self.menu = Menu(items, T.CANVAS_W // 2 - 140, 262, w=280, sound=app.sound)

    def play(self, quick=False):
        from .highlights import HighlightsScene

        report = self.g.play_week()
        self.g.save(save_path())
        results = ResultsScene(self.app, report)
        if report.player_result and not quick:
            self.app.replace(HighlightsScene(self.app, report, results))
        else:
            self.app.replace(results)

    def handle(self, ev):
        if is_back(ev):
            self.app.pop()
        else:
            self.menu.handle(ev)

    def draw(self, surf):
        g = self.g
        T.frame(surf)
        T.header(surf, g.event_label().upper(), g.season_label)
        if not self.fixture:
            T.big_text(surf, "NO MATCH THIS WEEK", (T.CANVAS_W // 2, 90), T.YELLOW, center=True)
            kind = g.calendar[g.week][0]
            if kind in ("lcup_group", "lcup"):
                status = g.league_cup_status()
                if kind == "lcup_group" and g.league_cup_group() is not None:
                    msg = "Your club has no League Cup game this matchday."
                elif status.startswith("Enter in"):
                    msg = "As a European club you enter the League Cup in the Second Round."
                elif status in ("Out", "Winners!"):
                    msg = "Your club is out of the League Cup." if status == "Out" else "League Cup winners!"
                else:
                    msg = "No League Cup game for your club this week."
            elif kind == "cup":
                status = g.cup_status()
                if status.startswith("Enter in"):
                    msg = f"Your club enters the Scottish Cup in the {status[len('Enter in ') :]}."
                elif g.club_name in g.cup.get("byes", []):
                    msg = "Your club has a bye this round."
                else:
                    msg = "You are out of the Scottish Cup."
            elif g.playoff_week() is not None:
                msg = (
                    "Your play-off tie is later on."
                    if g.in_playoffs()
                    else "Your season is over - the play-offs go on."
                )
            else:
                msg = "Your league programme is finished."
            T.text(surf, msg, (T.CANVAS_W // 2, 140), T.WHITE, center=True)
            T.text(surf, "The players get a week's rest.", (T.CANVAS_W // 2, 160), T.LIGHT_GREY, center=True)
            self.menu.draw(surf)
            return
        h, a, comp = self.fixture
        hc, ac = g.clubs[h], g.clubs[a]
        T.text(surf, comp, (T.CANVAS_W // 2, TOP + 4), T.LIGHT_GREY, center=True)
        T.big_text(surf, hc.short, (T.CANVAS_W // 2 - 150, TOP + 22), T.WHITE, center=True, scale=3)
        T.big_text(surf, "V", (T.CANVAS_W // 2, TOP + 30), T.YELLOW, center=True, scale=2)
        T.big_text(surf, ac.short, (T.CANVAS_W // 2 + 150, TOP + 22), T.WHITE, center=True, scale=3)
        T.text(
            surf, h, (T.CANVAS_W // 2 - 150, TOP + 76), T.YELLOW if h == g.club_name else T.WHITE, center=True
        )
        T.text(
            surf, a, (T.CANVAS_W // 2 + 150, TOP + 76), T.YELLOW if a == g.club_name else T.WHITE, center=True
        )
        T.kit_swatch(surf, T.CANVAS_W // 2 - 240, TOP + 30, hc.kit, 16, 20)
        T.kit_swatch(surf, T.CANVAS_W // 2 + 224, TOP + 30, T.away_kit(hc.kit, ac.kit), 16, 20)
        venue = data.NEUTRAL_VENUE if g.cup_neutral(comp) else hc.stadium
        T.text(surf, f"at {venue}", (T.CANVAS_W // 2, TOP + 96), T.LIGHT_GREY, center=True)

        hs = team_strength(g.selected_players(h))
        as_ = team_strength(g.selected_players(a))
        y = TOP + 120
        for label, hv, av in (
            ("DEFENCE", hs.defence, as_.defence),
            ("MIDFIELD", hs.midfield, as_.midfield),
            ("ATTACK", hs.attack, as_.attack),
            ("MORALE", hc.morale, ac.morale),
        ):
            T.text(surf, label, (T.CANVAS_W // 2, y), T.LIGHT_GREY, center=True, size=11)
            w = 180
            fill = int(w * min(1, hv / 99))
            pygame.draw.rect(surf, T.DARK_GREY, (T.CANVAS_W // 2 - 40 - w, y + 3, w, 8))
            pygame.draw.rect(surf, T.LIGHT_GREEN, (T.CANVAS_W // 2 - 40 - fill, y + 3, fill, 8))
            T.bar(surf, T.CANVAS_W // 2 + 40, y + 3, w, 8, av, 99, T.LIGHT_RED)
            y += 20
        tired = [p for p in g.selected_players(g.club_name) if p.energy < 70]
        if len(g.club.selected) < 11:
            T.text(
                surf,
                "You have fewer than 11 picked - the rest will be filled automatically.",
                (T.CANVAS_W // 2, 244),
                T.LIGHT_RED,
                center=True,
                size=11,
            )
        elif tired:
            # name as many as fit on the line, then "+N more"
            surnames = [p.name.split()[-1] for p in tired]
            max_w = T.CANVAS_W - 2 * T.BORDER - 20
            for shown in range(len(surnames), 0, -1):
                extra = f" +{len(surnames) - shown} more" if shown < len(surnames) else ""
                msg = f"Tired players in your XI: {', '.join(surnames[:shown])}{extra} - rest them?"
                if T.font(11).size(msg)[0] <= max_w:
                    break
            T.text(
                surf,
                msg,
                (T.CANVAS_W // 2, 244),
                T.LIGHT_RED,
                center=True,
                size=11,
            )
        self.menu.draw(surf)


class ResultsScene(Scene):
    def __init__(self, app, report):
        super().__init__(app)
        self.g: Game = app.game
        self.report = report
        self.page = 0  # 0 = this week's results, then one page per cup round played

    @property
    def pages(self) -> int:
        return 1 + len(self.report.cup_rounds)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN or (ev.type == pygame.MOUSEBUTTONDOWN):
            if self.page + 1 < self.pages:
                self.page += 1
            else:
                self.next()

    def next(self):
        g = self.g
        if self.report.season_summary:
            self.app.replace(SeasonEndScene(self.app, self.report.season_summary))
            return
        if g.sacked:
            self.app.replace(GameOverScene(self.app))
            return
        self.app.pop()

    def on_enter(self):
        self.app.sound.stop("goal")

    def draw_cup_page(self, surf, label, results):
        g = self.g
        T.frame(surf)
        T.header(surf, label.upper(), g.season_label)
        spfl = {c for d in g.divisions for c in d}
        per_col = max(8, (len(results) + 1) // 2)
        line_h = 12 if per_col > 14 else 14
        y0 = TOP + 6
        for i, r in enumerate(results):
            x = L + (i // per_col) * 300
            y = y0 + (i % per_col) * line_h
            home, away = cupmod.display_name(r.home), cupmod.display_name(r.away)
            if r.pens:  # mark who won the shoot-out
                if r.winner == r.home:
                    home += "*"
                else:
                    away += "*"
            text = f"{home:>20} {r.home_goals}-{r.away_goals}  {away}"
            if g.club_name in (r.home, r.away):
                col = T.YELLOW
            elif r.home in spfl or r.away in spfl:
                col = T.WHITE
            else:
                col = T.LIGHT_GREY
            T.text(surf, text, (x, y), col, size=10)
        y = y0 + per_col * line_h + 8
        T.text(surf, "* won on penalties   White: SPFL clubs   Grey: non-league", (L, y), T.GREY, size=10)
        if label.startswith("League Cup"):
            st = g.league_cup
            if st.get("winner"):
                T.text(surf, f"{st['winner']} win the League Cup!", (L, y + 16), T.YELLOW, size=11)
            elif g.league_cup_next_label():
                T.text(surf, f"Next: {g.league_cup_next_label()}", (L, y + 16), T.CYAN, size=11)
            group = g.league_cup_group()
            if "Group Matchday" in label and group is not None:
                gy = y + 34
                T.text(surf, f"GROUP {lcup.GROUP_NAMES[group]}", (L, gy), T.YELLOW, size=10, bold=True)
                T.text(surf, "P  W  PW PL  L   F  A  Pts", (L + 360, gy), T.GREY, size=10, right=True)
                for i, team in enumerate(lcup.standings(st, group)):
                    r = st["tables"][team]
                    colr = T.YELLOW if team == g.club_name else T.WHITE
                    ry = gy + 12 + i * 11
                    T.text(surf, team, (L, ry), colr, size=10)
                    line = f"{r['P']}  {r['W']}  {r['PW']}  {r['PL']}  {r['L']}  {r['F']:>2} {r['A']:>2}  {r['Pts']:>3}"
                    T.text(surf, line, (L + 360, ry), colr, size=10, right=True)
        else:
            cup = g.cup
            if cup.get("winner"):
                T.text(surf, f"{cup['winner']} win the Scottish Cup!", (L, y + 16), T.YELLOW, size=11)
            elif cup.get("ties") or cup.get("byes"):
                T.text(surf, f"Next: {g.cup_next_label()}", (L, y + 16), T.CYAN, size=11)
        more = self.page + 1 < self.pages
        T.footer(surf, "Press any key for the next results" if more else "Press any key to continue")

    def draw(self, surf):
        g, rep = self.g, self.report
        if self.page > 0:
            label, results = rep.cup_rounds[self.page - 1]
            self.draw_cup_page(surf, label, results)
            return
        T.frame(surf)
        T.header(surf, f"RESULTS - {rep.label.upper()}", g.season_label)
        y = TOP + 4
        if rep.player_result:
            r = rep.player_result
            T.big_text(
                surf,
                f"{g._short(r.home)} {r.home_goals} - {r.away_goals} {g._short(r.away)}",
                (T.CANVAS_W // 2, y),
                T.YELLOW,
                center=True,
            )
            if r.pens:
                T.text(
                    surf,
                    f"{r.winner} win {r.pens} on penalties",
                    (T.CANVAS_W // 2, y + 30),
                    T.WHITE,
                    center=True,
                    size=11,
                )
                y += 12
            if "play-off" in rep.player_comp:
                T.text(surf, rep.player_comp, (T.CANVAS_W // 2, y + 30), T.CYAN, center=True, size=11)
                y += 12
                mine = next((n for n in rep.news if "aggregate" in n and g.club_name in n), "")
                if mine:
                    won = f"{g.club_name} beat" in mine
                    T.text(
                        surf,
                        mine.split(": ", 1)[-1],
                        (T.CANVAS_W // 2, y + 30),
                        T.LIGHT_GREEN if won else T.LIGHT_RED,
                        center=True,
                        size=11,
                    )
                    y += 12
            y += 32
            goals = [e for e in r.events if e.kind == "goal"]
            rows = 0
            for side, x, right in (
                ("home", T.CANVAS_W // 2 - 20, True),
                ("away", T.CANVAS_W // 2 + 20, False),
            ):
                mine = [e for e in goals if e.side == side]
                for i, e in enumerate(mine):
                    T.text(surf, f"{e.player} {e.minute}'", (x, y + i * 13), T.WHITE, size=11, right=right)
                rows = max(rows, len(mine))
            y += rows * 13 + 8
        cup = not rep.label.startswith("League")
        lines = rep.results
        heading = "Other results"
        if rep.label.startswith("Play-offs"):
            heading = "Play-off results"
        elif cup:
            heading = "Cup results"
        if lines:
            T.text(surf, heading, (L, y), T.LIGHT_GREY, size=11)
            y += 14
        elif rep.cup_rounds:
            T.text(
                surf, f"All the {rep.cup_rounds[0][0]} results are on the next page.", (L, y), T.CYAN, size=11
            )
            y += 14
        shown = [r for r in lines if r is not rep.player_result][: 16 if cup else 8]
        col_w = 300
        for i, r in enumerate(shown):
            cx = L + (i // 8) * col_w
            cy = y + (i % 8) * 14
            score = f"{r.home_goals}-{r.away_goals}" + ("p" if r.pens else "")
            T.text(surf, f"{r.home[:18]:>18} {score:^5} {r.away[:18]}", (cx, cy), T.WHITE, size=11)
        y += min(8, len(shown)) * 14 + 8
        pos = g.position()
        T.text(
            surf,
            f"League position: {pos}  |  Bank: {T.money(g.balance)}  |  Week net: {T.money(rep.finance.get('Net', 0))}",
            (L, y),
            T.CYAN,
            size=11,
        )
        y += 18
        bottom = T.CANVAS_H - T.BORDER - 30
        for item in rep.news:
            if g.club_name in item:
                good = any(w in item.lower() for w in ("through", f"{g.club_name.lower()} beat", " win "))
                col = T.LIGHT_GREEN if good else T.LIGHT_RED
            else:
                col = T.LIGHT_GREY
            for line in T.wrap(item, 88):
                if y > bottom:
                    break
                T.text(surf, line, (L, y), col, size=10)
                y += 12
        if self.pages > 1:
            rounds = ", ".join(label for label, _ in rep.cup_rounds)
            T.footer(surf, f"Press any key: {rounds} results"[:96])
        else:
            T.footer(surf, "Press any key to continue")


class SeasonEndScene(Scene):
    def __init__(self, app, summary):
        super().__init__(app)
        self.s = summary

    def handle(self, ev):
        if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            if self.app.game.sacked:
                self.app.replace(GameOverScene(self.app))
            else:
                self.app.pop()

    def draw(self, surf):
        s = self.s
        T.frame(surf, T.YELLOW, T.BLUE)
        T.header(surf, f"END OF SEASON {s['season']}")
        y = TOP + 4
        T.big_text(
            surf, f"YOU FINISHED {ordinal(s['position'])}", (T.CANVAS_W // 2, y), T.YELLOW, center=True
        )
        y += 32
        T.text(
            surf,
            f"in the {s['division']}  -  prize money {T.money(s['prize'])}",
            (T.CANVAS_W // 2, y),
            T.WHITE,
            center=True,
        )
        y += 20
        for d in range(4):
            T.text(surf, f"{data.DIVISION_FULL[d]} champions:", (L + 20, y), T.LIGHT_GREY, size=12)
            T.text(surf, s["champions"][d], (L + 280, y), T.LIGHT_GREEN, size=12)
            y += 14
        T.text(surf, f"{data.CUP_NAME} winners:", (L + 20, y), T.LIGHT_GREY, size=12)
        T.text(surf, s.get("cup_winner", ""), (L + 280, y), T.CYAN, size=12)
        y += 14
        T.text(surf, "League Cup winners:", (L + 20, y), T.LIGHT_GREY, size=12)
        T.text(surf, s.get("league_cup_winner", ""), (L + 280, y), T.CYAN, size=12)
        y += 18
        for label, names, col in (
            ("Promoted: ", s["promoted"], T.LIGHT_GREEN),
            ("Relegated: ", s["relegated"], T.LIGHT_RED),
        ):
            for line in T.wrap(label + ", ".join(names), 84)[:2]:
                T.text(surf, line, (L + 20, y), col, size=11)
                y += 13
        y += 3
        for line in s.get("playoffs", []):
            T.text(surf, line[:90], (L + 20, y), T.CYAN, size=10)
            y += 12
        y += 4
        if s.get("top_scorer"):
            T.text(surf, f"Division top scorer: {s['top_scorer']}", (L + 20, y), T.WHITE, size=11)
            y += 16
        if s.get("new_division"):
            T.text(
                surf,
                f"Next season you will play in the {s['new_division']}.",
                (T.CANVAS_W // 2, y + 4),
                T.YELLOW,
                center=True,
            )
        T.footer(surf, "Press any key to start the new season")


class GameOverScene(Scene):
    def handle(self, ev):
        if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            from .intro import TitleScene

            try:
                save_path().unlink()
            except OSError:
                pass
            self.app.game = None
            self.app.reset(TitleScene(self.app))

    def draw(self, surf):
        T.frame(surf, T.RED, T.BLACK)
        g = self.app.game
        dropped = bool(g and "SPFL" in g.game_over_reason)
        title = "OUT OF THE SPFL!" if dropped else "YOU'RE SACKED!"
        T.big_text(surf, title, (T.CANVAS_W // 2, 110), T.LIGHT_RED, center=True, scale=3)
        if g:
            reason = g.game_over_reason or f"The board of {g.club.name} have run out of patience."
            T.text(surf, reason, (T.CANVAS_W // 2, 180), T.WHITE, center=True)
            seasons = len(g.history)
            T.text(
                surf,
                f"{g.manager} managed {seasons} full season(s).",
                (T.CANVAS_W // 2, 200),
                T.LIGHT_GREY,
                center=True,
            )
        T.text(surf, "Press any key", (T.CANVAS_W // 2, 260), T.GREY, center=True)


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def open_update(app):
    """Only runs when the player chooses Update: fetch this platform's installer in the
    browser (or open the release page if there's no installer for this system)."""
    info = app.update_info or {}
    target = info.get("download") or info.get("url")
    if target:
        webbrowser.open(target)
