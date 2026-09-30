"""Stats & Records: this season's numbers, the Golden Boot races, the roll of honour and the manager's record."""

from __future__ import annotations

import pygame

from ..core import data, stats
from ..core.game import Game
from . import theme as T
from .app import Scene
from .screens import TOP, L, is_back, ordinal
from .widgets import Table

# page ids, in LEFT/RIGHT order; "scorers<n>" is the Golden Boot race in division n
PAGES = ["club", "scorers0", "scorers1", "scorers2", "scorers3", "form", "honours", "manager"]
HEADER_H = 22  # T.header's black bar


def _club(name: str, width: int = 21) -> str:
    return name if len(name) <= width else name[: width - 1] + "."


class StatsScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.g: Game = app.game
        self.page = 0
        self.table: Table | None = None
        self.refresh()

    @property
    def page_id(self) -> str:
        return PAGES[self.page]

    def turn(self, step: int):
        self.page = (self.page + step) % len(PAGES)
        self.app.sound.play("blip")
        self.refresh()

    def _table(self, columns, y=TOP + 20, visible=14) -> Table:
        return Table(columns, L, y, 580, visible=visible, line_h=15, sound=self.app.sound)

    def refresh(self):
        g, pid = self.g, self.page_id
        self.table = None
        if pid == "club":
            self.table = self._table(
                [
                    ("Name", 0, "l"),
                    ("Pos", 170, "l"),
                    ("Age", 240, "r"),
                    ("Pl", 290, "r"),
                    ("Gls", 330, "r"),
                    ("Bk", 370, "r"),
                    ("Form", 392, "l"),
                ],
                y=TOP + 22,
                visible=13,
            )
            rows = []
            for p in stats.club_stats(g, g.club_name):
                color = T.WHITE if p.apps else T.LIGHT_GREY
                cells = [
                    p.name[:20],
                    p.pos,
                    str(p.age),
                    str(p.apps),
                    str(p.goals),
                    str(p.yellows or ""),
                    p.form_label,
                ]
                rows.append((cells, color, p.id))
            self.table.set_rows(rows)
        elif pid.startswith("scorers"):
            self.table = self._table(
                [
                    ("", 18, "r"),
                    ("Name", 28, "l"),
                    ("Club", 210, "l"),
                    ("Pl", 420, "r"),
                    ("Gls", 460, "r"),
                    ("Form", 482, "l"),
                ]
            )
            rows = []
            for i, p in enumerate(stats.top_scorers(g, int(pid[-1]))):
                color = T.YELLOW if p.club == g.club_name else T.WHITE
                rows.append(
                    (
                        [str(i + 1), p.name[:22], _club(p.club, 24), str(p.apps), str(p.goals), p.form_label],
                        color,
                        p.id,
                    )
                )
            self.table.set_rows(rows)
        elif pid == "form":
            self.table = self._table(
                [
                    ("", 18, "r"),
                    ("Name", 28, "l"),
                    ("Club", 200, "l"),
                    ("Division", 368, "l"),
                    ("Pl", 494, "r"),
                    ("Gls", 530, "r"),
                    ("Form", 544, "l"),
                ]
            )
            rows = []
            for i, p in enumerate(stats.in_form(g)):
                color = T.YELLOW if p.club == g.club_name else T.WHITE
                div = data.DIVISIONS[g.clubs[p.club].division]
                cells = [
                    str(i + 1),
                    p.name[:20],
                    _club(p.club, 20),
                    div,
                    str(p.apps),
                    str(p.goals),
                    p.form_label,
                ]
                rows.append((cells, color, p.id))
            self.table.set_rows(rows)
        elif pid == "honours":
            self.table = self._table(
                [
                    ("Season", 0, "l"),
                    ("Premiership", 72, "l"),
                    ("Scottish Cup", 244, "l"),
                    ("League Cup", 416, "l"),
                ]
            )
            rows = []
            for h in reversed(g.history):
                champions = h.get("champions") or ["-"]
                won = h["club"] in (champions[0], h.get("cup_winner"), h.get("league_cup_winner"))
                cells = [
                    h["season"],
                    _club(champions[0]),
                    _club(h.get("cup_winner") or "-"),
                    _club(h.get("league_cup_winner") or "-"),
                ]
                rows.append((cells, T.YELLOW if won else T.WHITE, h["season"]))
            self.table.set_rows(rows)

    # ------------------------------------------------------------------ input
    def handle(self, ev):
        if is_back(ev):
            self.app.pop()
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.turn(1 if ev.key == pygame.K_RIGHT else -1)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and ev.pos[1] < T.BORDER + HEADER_H:
            self.turn(1)  # click the title bar for the next page
        elif self.table:
            self.table.handle(ev)

    # ------------------------------------------------------------------ drawing
    def draw(self, surf):
        g, pid = self.g, self.page_id
        T.frame(surf)
        titles = {
            "club": f"{g.club_name.upper()} - SEASON STATS",
            "form": "IN FORM - THE SPFL'S HOTTEST PLAYERS",
            "honours": "ROLL OF HONOUR",
            "manager": f"MANAGER RECORD - {g.manager.upper()}",
        }
        title = titles.get(pid) or f"TOP SCORERS - {data.DIVISION_FULL[int(pid[-1])].upper()}"
        T.header(surf, title, f"{g.season_label}   page {self.page + 1}/{len(PAGES)}")
        if pid == "club":
            self.draw_club_summary(surf)
        if self.table:
            self.table.draw(surf)
        notes = {
            "form": f"Regulars ({stats.IN_FORM_MIN_APPS}+ games) on a good run. Form lifts a player up to 10%.",
            "honours": "Your club's trophies in yellow. Filled in at the end of each season.",
        }
        note = notes.get(pid) or (
            "Goals in all competitions this season. Your players in yellow."
            if pid.startswith("scorers")
            else ""
        )
        if self.table and not self.table.rows:
            empty = {
                "honours": "No seasons finished yet.",
                "form": "Nobody is on a hot streak yet.",
            }.get(pid, "No goals yet this season.")
            T.text(surf, empty, (L, TOP + 44), T.LIGHT_GREY)
        if pid == "manager":
            self.draw_manager(surf)
        if note:
            T.text(surf, note, (L, TOP + 4), T.CYAN)
        T.footer(surf, "LEFT/RIGHT or click the title bar: next page   Right-click/ESC: back")

    def draw_club_summary(self, surf):
        r = stats.season_record(self.g)
        line = (
            f"All competitions:  P {r['P']}   W {r['W']}   D {r['D']}   L {r['L']}   Goals {r['F']}-{r['A']}"
        )
        T.text(surf, line, (L, TOP + 4), T.CYAN)

    def draw_manager(self, surf):
        g = self.g
        rec = g.records
        y = TOP + 6

        def row(label, value, color=T.WHITE):
            nonlocal y
            T.text(surf, label, (L, y), T.LIGHT_GREY)
            T.text(surf, value, (L + 160, y), color)
            y += 16

        clubs = list(dict.fromkeys([h["club"] for h in g.history] + [g.club_name]))
        row("Seasons finished", f"{len(g.history)}   clubs: {', '.join(clubs)}"[:52])
        won = stats.trophies(g.history)
        row("Trophies", f"{len(won)}" if won else "None yet", T.YELLOW if won else T.WHITE)
        for t in won[-4:]:
            T.text(surf, t, (L + 160, y), T.YELLOW, size=11)
            y += 13
        best = stats.best_finish(g.history)
        row(
            "Best league finish",
            f"{ordinal(best['position'])} in the {best['division'][5:]} ({best['season']})" if best else "-",
        )
        for key, label in (("biggest_win", "Biggest win"), ("heaviest_defeat", "Heaviest defeat")):
            m = rec.get(key)
            row(
                label,
                f"{m['score']} v {_club(m['opponent'], 24)} ({m['venue']}), {m['season']}" if m else "-",
            )
            if m and m["competition"]:
                T.text(surf, m["competition"], (L + 160, y), T.LIGHT_GREY, size=11)
                y += 13
        ts = rec.get("top_scorer")
        row("Best season scorer", f"{ts['name']}, {ts['goals']} goals ({ts['season']})" if ts else "-")

        # career, most recent seasons first
        y += 6
        T.text(surf, "Season   Club                     Division       Pos   Pts", (L, y), T.TITLE, size=11)
        y += 14
        for h in list(reversed(g.history))[: max(0, (T.CANVAS_H - T.BORDER - 40 - y) // 13)]:
            div = h["division"][5:] if h["division"].startswith("SPFL ") else h["division"]
            line = f"{h['season']:<9}{_club(h['club'], 24):<25}{div:<15}{ordinal(h['position']):>4}{h.get('points', ''):>6}"
            T.text(surf, line, (L, y), T.WHITE, size=11)
            y += 13
        if not g.history:
            T.text(surf, "Your first season is still under way.", (L, y), T.LIGHT_GREY, size=11)
