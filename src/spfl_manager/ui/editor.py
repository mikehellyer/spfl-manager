"""Squad editor.

Two things can be edited with the same screens, each through a "backend":
  * DatabaseBackend - the squad database used when starting a NEW game
  * SaveBackend     - the career in progress (the current save game)
The save backend works on a copy of the game, so nothing changes until you save.
"""

from __future__ import annotations

import pygame

from ..core import data
from ..core.database import POSITIONS, SquadDB, user_file
from ..core.game import Game, save_path
from ..core.models import FORM_MAX
from . import theme as T
from .app import Scene
from .screens import TOP, L, MessageScene
from .widgets import Table

DIV_OF = {c.name: d for d, div in enumerate(data.CLUBS) for c in div}


# ----------------------------------------------------------------------------- form
class Field:
    def __init__(self, key, label, kind, value, lo=0, hi=99, choices=(), auto=None, estimate=None):
        self.key, self.label, self.kind, self.value = key, label, kind, value
        self.lo, self.hi, self.choices = lo, hi, choices
        # auto: None = no estimate for this field, True = showing the estimate, False = a real value
        self.auto = auto
        self.estimate = estimate
        self.touched = False
        self.typed = ""  # digits typed since the field was focused

    def set(self, v):
        self.value = v
        self.touched = True
        if self.auto is not None:
            self.auto = False

    def use_estimate(self):
        self.value, self.auto, self.touched = self.estimate, True, False


class Form:
    """Keyboard + mouse form. Fields: text, int, choice. Last row is Save / Cancel."""

    ROW_H = 24

    def __init__(self, fields, x, y, on_save, on_cancel, sound=None):
        self.fields = fields
        self.x, self.y = x, y
        self.focus = 0
        self.on_save, self.on_cancel = on_save, on_cancel
        self.sound = sound
        self.t = 0.0

    @property
    def rows(self):
        return len(self.fields) + 1  # + buttons row

    def _row_at(self, pos):
        i = (pos[1] - self.y) // self.ROW_H
        return i if 0 <= i < self.rows and self.x - 10 <= pos[0] <= self.x + 440 else None

    def _move(self, step):
        self.focus = (self.focus + step) % self.rows
        for f in self.fields:
            f.typed = ""
        if self.sound:
            self.sound.play("blip")

    def _adjust(self, f: Field, step: int):
        if f.kind == "int":
            f.set(max(f.lo, min(f.hi, f.value + step)))
        elif f.kind == "choice":
            i = f.choices.index(f.value) if f.value in f.choices else 0
            f.set(f.choices[(i + (1 if step > 0 else -1)) % len(f.choices)])

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
            self.on_cancel()  # right-click = back, as everywhere else
            return
        on_buttons = self.focus == len(self.fields)
        f = None if on_buttons else self.fields[self.focus]
        if ev.type == pygame.KEYDOWN:
            shift = ev.mod & pygame.KMOD_SHIFT
            if ev.key == pygame.K_ESCAPE:
                self.on_cancel()
            elif ev.key in (pygame.K_UP,) or (ev.key == pygame.K_TAB and shift):
                self._move(-1)
            elif ev.key in (pygame.K_DOWN, pygame.K_TAB):
                self._move(1)
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if on_buttons:
                    self.on_save()
                else:
                    self._move(1)
            elif on_buttons and ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
                pass
            elif f and ev.key in (
                pygame.K_LEFT,
                pygame.K_RIGHT,
                pygame.K_MINUS,
                pygame.K_EQUALS,
                pygame.K_PLUS,
            ):
                if f.kind != "text":
                    up = ev.key in (pygame.K_RIGHT, pygame.K_EQUALS, pygame.K_PLUS)
                    self._adjust(f, (5 if shift else 1) * (1 if up else -1))
            elif f and ev.key == pygame.K_DELETE and f.kind == "int" and f.auto is not None:
                f.use_estimate()
            elif f and ev.key == pygame.K_BACKSPACE:
                if f.kind == "text":
                    f.set(f.value[:-1])
                elif f.kind == "int":
                    f.typed = f.typed[:-1]
                    if f.typed:
                        f.set(max(f.lo, min(f.hi, int(f.typed))))
            elif f and ev.unicode:
                if f.kind == "text" and ev.unicode.isprintable() and len(f.value) < 28:
                    f.set(f.value + ev.unicode)
                elif f.kind == "int" and ev.unicode.isdigit():
                    f.typed = (f.typed + ev.unicode)[-2:]
                    f.set(max(f.lo, min(f.hi, int(f.typed))))
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            i = self._row_at(ev.pos)
            if i is None:
                return
            if i == len(self.fields):
                (self.on_save if ev.pos[0] < self.x + 220 else self.on_cancel)()
            else:
                self.focus = i
                fld = self.fields[i]
                if fld.kind != "text":  # click right half to increase, left half to decrease
                    self._adjust(fld, 1 if ev.pos[0] > self.x + 260 else -1)
        elif ev.type == pygame.MOUSEWHEEL and f and f.kind != "text":
            self._adjust(f, ev.y)

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        for i, f in enumerate(self.fields):
            y = self.y + i * self.ROW_H
            focused = i == self.focus
            if focused:
                pygame.draw.rect(surf, T.DARK_GREY, (self.x - 8, y - 3, 456, self.ROW_H - 2))
            T.text(surf, f.label, (self.x, y), T.YELLOW if focused else T.LIGHT_GREY)
            vx = self.x + 150
            if f.kind == "text":
                pygame.draw.rect(surf, T.BLACK, (vx - 4, y - 2, 290, 18))
                w = T.text(surf, f.value, (vx, y), T.WHITE)
                if focused and int(self.t * 2) % 2 == 0:
                    pygame.draw.rect(surf, T.LIGHT_BLUE, (vx + w + 1, y, 7, 13))
            else:
                shown = str(f.value)
                T.text(surf, "<", (vx, y), T.CYAN if focused else T.GREY)
                T.text(surf, shown, (vx + 50, y), T.WHITE, center=True)
                T.text(surf, ">", (vx + 92, y), T.CYAN if focused else T.GREY)
                if f.auto:
                    T.text(surf, "(estimate)", (vx + 116, y), T.GREY, size=11)
                elif f.auto is False:
                    T.text(surf, "(set - DEL resets)", (vx + 116, y), T.LIGHT_GREEN, size=11)
        y = self.y + len(self.fields) * self.ROW_H + 6
        on_buttons = self.focus == len(self.fields)
        for j, label in enumerate(("SAVE", "CANCEL")):
            bx = self.x + j * 220
            pygame.draw.rect(surf, T.HILITE if on_buttons and j == 0 else T.BLACK, (bx, y, 200, 20))
            pygame.draw.rect(surf, T.LIGHT_BLUE, (bx, y, 200, 20), 1)
            T.text(
                surf,
                label,
                (bx + 100, y + 3),
                T.BLACK if on_buttons and j == 0 else T.WHITE,
                center=True,
                bold=True,
            )


# ----------------------------------------------------------------------------- backends
class DatabaseBackend:
    """The squad database used for new games."""

    title = "SQUAD DATABASE"
    can_rate = True
    can_reset = True
    note = "Changes apply to NEW games"
    columns = [
        ("No", 0, "l"),
        ("Name", 30, "l"),
        ("Pos", 260, "l"),
        ("Skill", 330, "r"),
        ("Age", 380, "r"),
        ("Notes", 400, "l"),
    ]
    legend = "~ = estimate (not set yet)   green = set by you   changes apply to NEW games"

    def __init__(self):
        self.db = SquadDB.load()

    @property
    def source(self) -> str:
        return "YOUR EDITED SQUADS" if self.db.custom else "ORIGINAL WIKIPEDIA SQUADS"

    def divisions(self) -> list[list[str]]:
        return [[c.name for c in div] for div in data.CLUBS]

    def players(self, club):
        return list(self.db.squad(club))

    def pos(self, p) -> str:
        return p.get("pos", "")

    def name(self, p) -> str:
        return p["name"]

    def row(self, club, r):
        skill, age, es, ea = self.db.stats(club, r)
        notes = (["loan"] if r.get("loan") else []) + (["~ estimate"] if es or ea else [])
        color = T.LIGHT_GREEN if ("skill" in r or "age" in r) else (T.LIGHT_GREY if es or ea else T.WHITE)
        cells = [
            r.get("no", ""),
            r["name"][:28],
            r["pos"],
            f"{skill}{'~' if es else ''}",
            f"{age}{'~' if ea else ''}",
            "  ".join(notes),
        ]
        return cells, color

    def rating(self, club) -> int:
        return self.db.rating(club)

    def set_rating(self, club, value):
        self.db.ratings[club] = max(1, min(99, value))

    def fields(self, club, r):
        r = r or {"name": "", "pos": "MID", "no": ""}
        skill, age, est_skill, est_age = self.db.stats(club, r)
        bare = {k: v for k, v in r.items() if k not in ("skill", "age")}
        est_skill_value, est_age_value, _, age_unknown = self.db.stats(club, bare)
        try:
            number = int(r.get("no") or 0)
        except ValueError:
            number = 0
        age_field = Field("age", "Age (in 2026)", "int", age, 15, 45, auto=est_age, estimate=est_age_value)
        if not age_unknown:
            age_field.auto = None  # age comes from a real date of birth
        return [
            Field("name", "Name", "text", r.get("name", "")),
            Field("no", "Shirt number", "int", number, 0, 99),
            Field("pos", "Position", "choice", r.get("pos", "MID"), choices=POSITIONS),
            Field("skill", "Skill (1-99)", "int", skill, 1, 99, auto=est_skill, estimate=est_skill_value),
            age_field,
            Field("loan", "On loan here", "choice", "Yes" if r.get("loan") else "No", choices=("No", "Yes")),
        ]

    def apply(self, club, r, f: dict) -> str:
        new = r is None
        r = r if r is not None else {}
        r["name"] = f["name"].value
        r["no"] = str(f["no"].value) if f["no"].value else ""
        r["pos"] = f["pos"].value
        for key in ("skill", "age"):
            fld = f[key]
            if fld.auto:
                r.pop(key, None)
            elif fld.touched:
                r[key] = int(fld.value)
        if f["loan"].value == "Yes":
            r["loan"] = True
        else:
            r.pop("loan", None)
        if new:
            self.db.add_player(club, r)
        else:
            self.db.sort(club)
        return ""

    def delete(self, club, r) -> str:
        self.db.remove_player(club, r)
        return ""

    def move(self, club, r, dest) -> str:
        self.db.move_player(r, club, dest)
        return ""

    def save(self):
        self.db.save()

    def reset(self):
        self.db = SquadDB.reset()


class SaveBackend:
    """The career in progress. Works on a copy until saved."""

    title = "EDIT SAVE GAME"
    can_rate = False
    can_reset = False
    columns = [
        ("Name", 0, "l"),
        ("Pos", 200, "l"),
        ("Skill", 272, "r"),
        ("Age", 312, "r"),
        ("Fit", 360, "r"),
        ("Inj", 400, "r"),
        ("Pl", 434, "r"),
        ("Gls", 466, "r"),
        ("Form", 478, "l"),
        ("Notes", 522, "l"),
    ]
    legend = "Changes apply to your CURRENT career when you save.   Yellow = in the starting XI"

    def __init__(self, app, game: Game | None = None):
        self.app = app
        source = game or app.game or Game.load(save_path())
        self.game = source.copy()

    @property
    def source(self) -> str:
        g = self.game
        return f"{g.manager.upper()} - {g.club_name.upper()} {g.season_label}"

    def divisions(self) -> list[list[str]]:
        return [list(d) for d in self.game.divisions]

    def players(self, club):
        return self.game.squad(club)

    def pos(self, p) -> str:
        return p.pos

    def name(self, p) -> str:
        return p.name

    def row(self, club, p):
        picked = p.id in self.game.clubs[club].selected
        notes = "PICKED" if picked else ""
        color = T.LIGHT_RED if p.injury else (T.YELLOW if picked else T.WHITE)
        cells = [
            p.name[:24],
            p.pos,
            str(p.skill),
            str(p.age),
            f"{p.energy}%",
            str(p.injury or ""),
            str(p.apps),
            str(p.goals),
            p.form_label,
            notes,
        ]
        return cells, color

    def rating(self, club) -> int:
        return self.game.clubs[club].rating

    def set_rating(self, club, value):
        pass

    def fields(self, club, p):
        return [
            Field("name", "Name", "text", p.name if p else ""),
            Field("pos", "Position", "choice", p.pos if p else "MID", choices=POSITIONS),
            Field("skill", "Skill (1-99)", "int", p.skill if p else self.rating(club), 1, 99),
            Field("age", "Age", "int", p.age if p else 21, 15, 45),
            Field("energy", "Fitness %", "int", p.energy if p else 100, 0, 100),
            Field("injury", "Injured (weeks)", "int", p.injury if p else 0, 0, 30),
            Field(
                "form", f"Form ({-FORM_MAX} to {FORM_MAX})", "int", p.form if p else 0, -FORM_MAX, FORM_MAX
            ),
        ]

    def apply(self, club, p, f: dict) -> str:
        if p is None:
            p = self.game.add_player(club, f["name"].value, f["pos"].value, f["skill"].value, f["age"].value)
        p.name = f["name"].value
        p.pos = f["pos"].value
        p.skill = f["skill"].value
        p.age = f["age"].value
        p.energy = f["energy"].value
        p.injury = f["injury"].value
        p.form = f["form"].value
        sel = self.game.clubs[club].selected
        if p.injury and p.id in sel:
            sel.remove(p.id)
        return ""

    def delete(self, club, p) -> str:
        return self.game.remove_player(p.id)

    def move(self, club, p, dest) -> str:
        return self.game.move_player(p.id, dest)

    def save(self):
        self.game.save(save_path())
        self.app.game = self.game  # the hub (if open) now shows the edited career
        self.game = self.game.copy()  # keep editing on a fresh copy

    def reset(self):
        pass


# ----------------------------------------------------------------------------- player form
class PlayerFormScene(Scene):
    def __init__(self, app, editor: EditorScene, club: str, player):
        super().__init__(app)
        self.editor, self.club, self.player = editor, club, player
        self.fields = editor.backend.fields(club, player)
        self.by_key = {f.key: f for f in self.fields}
        self.form = Form(self.fields, L + 60, TOP + 60, self.save, app.pop, sound=app.sound)
        self.error = ""

    def save(self):
        name = " ".join(self.by_key["name"].value.split())
        if not name:
            self.error = "The player needs a name."
            return
        self.by_key["name"].value = name
        err = self.editor.backend.apply(self.club, self.player, self.by_key)
        if err:
            self.error = err
            return
        self.editor.changed(f"{name} saved.")
        self.app.pop()

    def handle(self, ev):
        self.form.handle(ev)

    def update(self, dt):
        self.form.update(dt)

    def draw(self, surf):
        T.frame(surf)
        T.header(surf, "NEW PLAYER" if self.player is None else "EDIT PLAYER", self.club)
        T.text(
            surf,
            "UP/DOWN: choose field   LEFT/RIGHT or type digits: change value   SHIFT: steps of 5",
            (L, TOP + 10),
            T.LIGHT_GREY,
            size=11,
        )
        hint = "Mouse: click < > or use the wheel"
        if isinstance(self.editor.backend, DatabaseBackend):
            hint = "DEL on skill/age: go back to the automatic estimate   " + hint
        T.text(surf, hint, (L, TOP + 26), T.LIGHT_GREY, size=11)
        self.form.draw(surf)
        if self.error:
            T.text(surf, self.error, (L + 60, TOP + 250), T.LIGHT_RED)
        T.footer(surf, "RETURN on SAVE to keep changes   Right-click/ESC: cancel")


# ----------------------------------------------------------------------------- club picker
class ClubPickerScene(Scene):
    def __init__(self, app, title, divisions, on_pick, exclude=""):
        super().__init__(app)
        self.title, self.on_pick = title, on_pick
        self.table = Table(
            [("Club", 0, "l"), ("Division", 300, "l")],
            L,
            TOP + 6,
            580,
            visible=17,
            line_h=15,
            on_activate=self.pick,
            sound=app.sound,
        )
        rows = [
            ([c, data.DIVISION_FULL[d]], T.WHITE, c)
            for d, div in enumerate(divisions)
            for c in div
            if c != exclude
        ]
        self.table.set_rows(rows)

    def pick(self, name):
        self.app.pop()
        self.on_pick(name)

    def handle(self, ev):
        if (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE) or (
            ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3
        ):
            self.app.pop()
        else:
            self.table.handle(ev)

    def draw(self, surf):
        T.frame(surf)
        T.header(surf, self.title)
        self.table.draw(surf)
        T.footer(surf, "RETURN/double-click: choose   Right-click/ESC: cancel")


# ----------------------------------------------------------------------------- editor
class EditorScene(Scene):
    def __init__(self, app, backend=None):
        super().__init__(app)
        self.backend = backend or DatabaseBackend()
        self.dirty = False
        divs = self.backend.divisions()
        self.division = 3
        if isinstance(self.backend, SaveBackend):
            self.division = self.backend.game.club.division
        self.club: str | None = None
        self.msg = ""
        self.clubs_table = Table(
            [
                ("Club", 0, "l"),
                ("Players", 250, "r"),
                ("GK", 290, "r"),
                ("DEF", 330, "r"),
                ("MID", 370, "r"),
                ("ATT", 410, "r"),
                ("Strength", 490, "r"),
            ],
            L,
            TOP + 26,
            580,
            visible=12,
            line_h=17,
            on_activate=self.open_club,
            sound=app.sound,
        )
        self.players_table = Table(
            self.backend.columns,
            L,
            TOP + 26,
            580,
            visible=15,
            line_h=15,
            on_activate=self.edit_player,
            sound=app.sound,
        )
        self.refresh()
        if isinstance(self.backend, SaveBackend) and self.backend.game.club_name in divs[self.division]:
            self.clubs_table.index = divs[self.division].index(self.backend.game.club_name)

    # data -----------------------------------------------------------------
    def changed(self, msg=""):
        self.dirty = True
        self.msg = msg
        self.refresh()

    def on_enter(self):
        self.refresh()

    def refresh(self):
        b = self.backend
        if self.club is None:
            rows = []
            for name in b.divisions()[self.division]:
                sq = b.players(name)
                cnt = {p: sum(1 for r in sq if b.pos(r) == p) for p in POSITIONS}
                thin = cnt["GK"] < 2 or cnt["DEF"] < 4 or cnt["MID"] < 4 or cnt["ATT"] < 2
                rows.append(
                    (
                        [
                            name,
                            str(len(sq)),
                            str(cnt["GK"]),
                            str(cnt["DEF"]),
                            str(cnt["MID"]),
                            str(cnt["ATT"]),
                            str(b.rating(name)),
                        ],
                        T.LIGHT_RED if thin else T.WHITE,
                        name,
                    )
                )
            self.clubs_table.set_rows(rows)
        else:
            rows = []
            for p in b.players(self.club):
                cells, color = b.row(self.club, p)
                rows.append((cells, color, p))
            self.players_table.set_rows(rows)

    # club level ------------------------------------------------------------
    def open_club(self, name):
        self.club = name
        self.players_table.index = self.players_table.top = 0
        self.msg = ""
        self.refresh()

    def set_rating(self, step):
        name = self.clubs_table.current
        if name and self.backend.can_rate:
            self.backend.set_rating(name, self.backend.rating(name) + step)
            self.changed(
                f"{name} strength {self.backend.rating(name)} - players' estimated skills follow it."
            )

    # player level ------------------------------------------------------------
    def edit_player(self, p):
        if p is not None:
            self.app.push(PlayerFormScene(self.app, self, self.club, p))

    def new_player(self):
        self.app.push(PlayerFormScene(self.app, self, self.club, None))

    def delete_player(self):
        p = self.players_table.current
        if p is None:
            return
        name = self.backend.name(p)

        def yes():
            err = self.backend.delete(self.club, p)
            if err:
                self.msg = err
            else:
                self.changed(f"{name} deleted.")

        self.app.push(
            MessageScene(self.app, "DELETE PLAYER", [f"Remove {name} from {self.club}?"], on_yes=yes)
        )

    def move_player(self):
        p = self.players_table.current
        if p is None:
            return
        src, name = self.club, self.backend.name(p)

        def picked(dest):
            err = self.backend.move(src, p, dest)
            if err:
                self.msg = err
            else:
                self.changed(f"{name} moved to {dest}.")

        self.app.push(
            ClubPickerScene(
                self.app, f"MOVE {name.upper()} TO...", self.backend.divisions(), picked, exclude=src
            )
        )

    # file level ---------------------------------------------------------------
    def save(self):
        try:
            self.backend.save()
        except OSError as exc:
            self.app.push(MessageScene(self.app, "SAVE FAILED", [str(exc)]))
            return
        self.dirty = False
        self.msg = "Saved." + (
            "  New games will use your edited squads."
            if self.backend.can_reset
            else "  Your career has been updated."
        )
        self.refresh()

    def reset(self):
        if not self.backend.can_reset:
            return

        def yes():
            self.backend.reset()
            self.club = None
            self.changed("Back to the original Wikipedia squads.")
            self.dirty = False

        self.app.push(
            MessageScene(
                self.app,
                "RESET ALL EDITS",
                ["Throw away ALL your edits and go back to the original squads?", "This can't be undone."],
                on_yes=yes,
            )
        )

    def leave(self):
        if not self.dirty:
            self.app.pop()
            return

        def save_and_leave():
            self.save()
            if not self.dirty:
                self.app.pop()

        self.app.push(
            MessageScene(
                self.app,
                "UNSAVED CHANGES",
                ["Save your changes before leaving?", "(ESC to stay in the editor)"],
                on_yes=save_and_leave,
                on_no=self.app.pop,
                yes_label="Save",
                no_label="Discard",
                esc_cancels=True,
            )
        )

    # input / draw -----------------------------------------------------------
    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
            # right-click = back, exactly like ESC
            ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="", mod=0)
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k == pygame.K_s:
                self.save()
                return
            if self.club is None:
                if k == pygame.K_ESCAPE:
                    self.leave()
                elif k in (pygame.K_LEFT, pygame.K_RIGHT):
                    self.division = (self.division + (1 if k == pygame.K_RIGHT else -1)) % 4
                    self.clubs_table.index = self.clubs_table.top = 0
                    self.refresh()
                elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    self.set_rating(1)
                elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.set_rating(-1)
                elif k == pygame.K_r:
                    self.reset()
                else:
                    self.clubs_table.handle(ev)
            else:
                if k in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    self.club = None
                    self.msg = ""
                    self.refresh()
                elif k == pygame.K_n:
                    self.new_player()
                elif k in (pygame.K_d, pygame.K_DELETE):
                    self.delete_player()
                elif k == pygame.K_m:
                    self.move_player()
                elif k == pygame.K_e:
                    self.edit_player(self.players_table.current)
                else:
                    self.players_table.handle(ev)
        else:
            (self.clubs_table if self.club is None else self.players_table).handle(ev)

    def draw(self, surf):
        b = self.backend
        T.frame(surf, T.LIGHT_BLUE if b.can_reset else T.ORANGE)
        source = b.source + ("  *UNSAVED*" if self.dirty else "")
        if self.club is None:
            T.header(surf, b.title, source)
            T.text(surf, data.DIVISION_FULL[self.division], (L, TOP + 6), T.YELLOW, bold=True)
            T.text(
                surf,
                "<  LEFT/RIGHT: division  >",
                (T.CANVAS_W - L - 4, TOP + 6),
                T.LIGHT_GREY,
                size=11,
                right=True,
            )
            self.clubs_table.draw(surf)
            y = TOP + 26 + 13 * 17 + 4
            T.text(surf, "Red: squad is short of a position.", (L, y), T.LIGHT_GREY, size=11)
            if b.can_rate:
                T.text(
                    surf,
                    "Strength sets the estimated skill of players you haven't rated yourself.",
                    (L, y + 13),
                    T.LIGHT_GREY,
                    size=11,
                )
            else:
                T.text(
                    surf,
                    "You're editing your current career - nothing changes until you press S.",
                    (L, y + 13),
                    T.YELLOW,
                    size=11,
                )
            if self.msg:
                T.text(surf, self.msg, (L, y + 30), T.CYAN, size=11)
            keys = (
                "RETURN: open club   +/-: strength   S: save   R: reset all   Right-click/ESC: exit"
                if b.can_reset
                else "RETURN: open club   S: save   Right-click/ESC: exit"
            )
            T.footer(surf, keys)
        else:
            divs = b.divisions()
            d = next((i for i, div in enumerate(divs) if self.club in div), 0)
            T.header(surf, self.club.upper(), source)
            T.text(
                surf,
                f"{data.DIVISION_FULL[d]}  -  strength {b.rating(self.club)}  -  {len(b.players(self.club))} players",
                (L, TOP + 6),
                T.YELLOW,
            )
            self.players_table.draw(surf)
            y = TOP + 26 + 16 * 15 + 2
            T.text(surf, self.msg or b.legend, (L, y), T.CYAN if self.msg else T.LIGHT_GREY, size=11)
            T.footer(surf, "RETURN/E: edit  N: new  D: delete  M: move  S: save  Right-click/ESC: clubs")


# ----------------------------------------------------------------------------- chooser
def open_editor(app):
    """From the title screen: choose between the squad database and the current save."""
    if not save_path().exists():
        app.push(EditorScene(app))
        return

    def edit_save():
        try:
            backend = SaveBackend(app)
        except Exception as exc:  # old or damaged save
            app.push(MessageScene(app, "CAN'T OPEN SAVE", [str(exc)]))
            return
        app.push(EditorScene(app, backend))

    app.push(
        MessageScene(
            app,
            "SQUAD EDITOR",
            [
                "What would you like to edit?",
                "",
                "Squad database: the players every NEW game starts with.",
                "Current save: your career in progress.",
            ],
            on_yes=lambda: app.push(EditorScene(app)),
            on_no=edit_save,
            yes_label="Squad database",
            no_label="Current save",
            esc_cancels=True,
        )
    )


def edits_file_label() -> str:
    return str(user_file())
