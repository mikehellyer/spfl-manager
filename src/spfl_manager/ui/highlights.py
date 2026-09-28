"""Match highlights - FM2 style animated chances on a perspective pitch.

Pitch coordinates are in metres: x 0..105 (goal to goal), y 0..68 (far to
near touchline), z is height. `project()` maps them to the screen.
"""

from __future__ import annotations

import math
import random

import pygame

from . import theme as T
from .app import Scene

PITCH_TOP, PITCH_BOTTOM = 112, 344
FAR_W, NEAR_W = 460, 610
CX = T.CANVAS_W // 2
GOAL_Y1, GOAL_Y2 = 30.34, 37.66
SKIN = (240, 190, 150)
KEEPER_KITS = [((200, 230, 60), (30, 30, 30), "", (0, 0, 0)), ((240, 140, 40), (30, 30, 30), "", (0, 0, 0))]


def project(x, y, z=0.0):
    t = y / 68
    w = FAR_W + t * (NEAR_W - FAR_W)
    s = w / NEAR_W
    sx = CX + (x / 105 - 0.5) * w
    sy = PITCH_TOP + t * (PITCH_BOTTOM - PITCH_TOP) - z * 9 * s
    return sx, sy, s


def lerp(a, b, f):
    return a + (b - a) * f


# ----------------------------------------------------------------------------- sprites
class Sprite:
    def __init__(self, x, y, kit, speed=7.0):
        self.x, self.y = x, y
        self.tx, self.ty = x, y
        self.kit = kit
        self.shorts = kit[1]
        self.speed = speed
        self.phase = random.random() * 6
        self.moving = False
        self.dive = 0.0  # keeper dive lean (-1..1)

    def update(self, dt):
        dx, dy = self.tx - self.x, self.ty - self.y
        d = math.hypot(dx, dy)
        step = self.speed * dt
        self.moving = d > 0.3
        if d <= step:
            self.x, self.y = self.tx, self.ty
        else:
            self.x += dx / d * step
            self.y += dy / d * step
        if self.moving:
            self.phase += dt * 14

    def draw(self, surf):
        sx, sy, s = project(self.x, self.y)
        sx, sy = int(sx), int(sy)
        k = max(0.7, s * 1.25)
        pygame.draw.ellipse(surf, (30, 90, 30), (sx - 5 * k, sy - 2 * k, 10 * k, 4 * k))
        lean = int(self.dive * 6 * k)
        # legs
        stride = int(math.sin(self.phase) * 3 * k) if self.moving else 0
        pygame.draw.line(surf, SKIN, (sx - 1 * k + lean // 2, sy - 6 * k), (sx - 2 * k + stride, sy), max(1, int(2 * k)))
        pygame.draw.line(surf, SKIN, (sx + 1 * k + lean // 2, sy - 6 * k), (sx + 2 * k - stride, sy), max(1, int(2 * k)))
        # shorts, shirt, head
        pygame.draw.rect(surf, self.shorts, (sx - 3 * k + lean // 2, sy - 9 * k, 6 * k, 4 * k))
        T.draw_shirt(surf, (sx - 3.5 * k + lean, sy - 16 * k, 7 * k, 8 * k), self.kit)
        pygame.draw.rect(surf, T.BLACK, (sx - 3.5 * k + lean, sy - 16 * k, 7 * k, 8 * k), 1)
        pygame.draw.circle(surf, SKIN, (sx + lean, int(sy - 19 * k)), max(2, int(3 * k)))


class Chance:
    """One scripted attacking move ending in a shot with a known outcome."""

    def __init__(self, rng, direction, outcome, atk_kit, def_kit, keeper_kit):
        self.rng, self.dir, self.outcome = rng, direction, outcome
        self.t = 0.0
        self.kicks: list[float] = []

        # waypoints in "attack space": u towards goal at 105
        u, v = rng.uniform(38, 55), rng.uniform(14, 54)
        wps = [(u, v)]
        for _ in range(rng.randint(2, 3)):
            u = min(84, u + rng.uniform(10, 18))
            v = max(10, min(58, v + rng.uniform(-18, 18)))
            wps.append((u, v))
        wps.append((rng.uniform(84, 94), rng.uniform(22, 46)))
        self.wps = wps

        segs = []  # (t0, t1, (u0,v0,z0), (u1,v1,z1), arc)
        t = 0.3
        for a, b in zip(wps, wps[1:]):
            dur = math.hypot(b[0] - a[0], b[1] - a[1]) / 28 + 0.2
            arc = rng.choice([0, 0, 1.2])
            segs.append((t, t + dur, (*a, 0), (*b, 0), arc))
            self.kicks.append(t)
            t += dur + rng.uniform(0.1, 0.25)  # a touch before the next pass
        self.shot_time = t
        sx, sy = wps[-1]
        keeper_y = 34.0
        if outcome == "goal":
            ty = rng.choice([rng.uniform(30.9, 32.5), rng.uniform(35.5, 37.1)])
            tz = rng.uniform(0.2, 2.0)
            segs.append((t, t + 0.45, (sx, sy, 0.3), (105.8, ty, tz), 0.4))
            segs.append((t + 0.45, t + 0.9, (105.8, ty, tz), (107.2, ty + rng.uniform(-0.4, 0.4), 0), 0))
            self.keeper_target = (104.5, 34 + (34 - ty) * 0.4)  # wrong way!
        elif outcome == "saved":
            ty = rng.uniform(32, 36)
            tz = rng.uniform(0.3, 1.6)
            segs.append((t, t + 0.5, (sx, sy, 0.3), (104.2, ty, tz), 0.3))
            segs.append((t + 0.5, t + 1.2, (104.2, ty, tz), (104.2, ty, tz), 0))
            self.keeper_target = (104.2, ty)
            keeper_y = ty
        elif outcome == "post":
            ty = rng.choice([GOAL_Y1, GOAL_Y2])
            segs.append((t, t + 0.45, (sx, sy, 0.3), (105, ty, 1.2), 0.3))
            back = (rng.uniform(92, 97), 34 + rng.uniform(-12, 12), 0)
            segs.append((t + 0.45, t + 1.1, (105, ty, 1.2), back, 1.0))
            self.keeper_target = (104.5, ty + (1.5 if ty < 34 else -1.5))
        else:  # miss
            if rng.random() < 0.4:
                ty, tz = rng.uniform(31, 37), 3.4  # over the bar
            else:
                ty, tz = rng.choice([rng.uniform(26, 29.8), rng.uniform(38.2, 42)]), rng.uniform(0.2, 1.5)
            segs.append((t, t + 0.55, (sx, sy, 0.3), (106, ty, tz), 0.4))
            segs.append((t + 0.55, t + 1.2, (106, ty, tz), (112, ty + (ty - 34) * 0.3, 0), 0.8))
            self.keeper_target = (104.5, 34 + (ty - 34) * 0.3)
        self.kicks.append(t)
        self.segs = segs
        self.duration = segs[-1][1] + 0.3
        self.keeper_y = keeper_y

        # players
        self.attackers = []
        for i, (wu, wv) in enumerate(wps[1:]):
            su, sv = self._to_xy(wu - rng.uniform(8, 16), wv + rng.uniform(-8, 8))
            self.attackers.append(Sprite(su, sv, atk_kit, speed=rng.uniform(7, 9)))
        su, sv = self._to_xy(*wps[0])
        self.carrier = Sprite(su, sv, atk_kit)
        self.attackers.insert(0, self.carrier)
        self.defenders = []
        for i in range(4):
            du, dv = rng.uniform(70, 92), 18 + i * 10 + rng.uniform(-3, 3)
            x, y = self._to_xy(du, dv)
            self.defenders.append(Sprite(x, y, def_kit, speed=rng.uniform(5.5, 7)))
        kx, ky = self._to_xy(104, 34)
        self.keeper = Sprite(kx, ky, keeper_kit, speed=6)
        self.sprites = self.attackers + self.defenders + [self.keeper]
        self.ball = self._to_xy(*wps[0]) + (0.0,)
        self.def_offsets = [(rng.uniform(4, 14), rng.uniform(-9, 9)) for _ in self.defenders]

    def _to_xy(self, u, v):
        return (u, v) if self.dir > 0 else (105 - u, 68 - v)

    def ball_at(self, t):
        if t <= self.segs[0][0]:
            u, v, z = self.segs[0][2]
            return u, v, z
        for i, (t0, t1, a, b, arc) in enumerate(self.segs):
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                return lerp(a[0], b[0], f), lerp(a[1], b[1], f), lerp(a[2], b[2], f) + 4 * arc * f * (1 - f)
            nxt = self.segs[i + 1][0] if i + 1 < len(self.segs) else None
            if nxt is not None and t1 < t < nxt:
                return b  # at the feet of the receiver
        return self.segs[-1][3]

    @property
    def done(self):
        return self.t >= self.duration

    def update(self, dt) -> list[str]:
        """Advance time; returns sound cues."""
        cues = []
        prev = self.t
        self.t += dt
        for k in self.kicks:
            if prev < k <= self.t:
                cues.append("kick")
        u, v, z = self.ball_at(self.t)
        self.ball = (*self._to_xy(u, v), z)

        # attackers: receiver i runs onto waypoint i
        seg_idx = sum(1 for s in self.segs if s[0] <= self.t)
        for i, spr in enumerate(self.attackers):
            if i < len(self.wps):
                if i >= seg_idx - 1:
                    spr.tx, spr.ty = self._to_xy(*self.wps[i])
                else:  # already passed - support the attack
                    spr.tx, spr.ty = self._to_xy(min(96, u - 6 + i * 2), v + (i - 2) * 6)
        # defenders close down between ball and goal
        for spr, (du, dv) in zip(self.defenders, self.def_offsets):
            gu = u + (105 - u) * 0.25 + du * 0.3
            spr.tx, spr.ty = self._to_xy(min(101, gu), v * 0.5 + 34 * 0.5 + dv)
        # keeper tracks the ball, then dives at the shot
        if self.t < self.shot_time:
            self.keeper.tx, self.keeper.ty = self._to_xy(103.5, max(31, min(37, 34 + (v - 34) * 0.3)))
        else:
            kx, ky = self._to_xy(*self.keeper_target)
            self.keeper.tx, self.keeper.ty = kx, ky
            self.keeper.speed = 9
            side = 1 if (self.keeper_target[1] > 34) == (self.dir > 0) else -1
            self.keeper.dive = min(1.0, (self.t - self.shot_time) * 4) * side * 0.8
        for spr in self.sprites:
            spr.update(dt)
        return cues


# ----------------------------------------------------------------------------- scene
class HighlightsScene(Scene):
    def __init__(self, app, report, next_scene):
        super().__init__(app)
        self.g = app.game
        self.res = report.player_result
        self.label = report.label
        self.comp = report.player_comp or report.label
        self.next_scene = next_scene
        self.rng = random.Random()
        hc, ac = self.g.clubs[self.res.home], self.g.clubs[self.res.away]
        self.hc, self.ac = hc, ac
        self.kits = {
            "home": hc.kit,
            "away": T.away_kit(hc.kit, ac.kit),
        }
        self.events = list(self.res.events)
        self.idx = 0
        self.score = [0, 0]
        self.minute = 0.0
        self.phase = "kickoff"
        self.timer = 2.0
        self.caption = "KICK OFF!"
        self.caption_col = T.WHITE
        self.commentary = f"Welcome to {hc.stadium} for {self.label.lower().replace('league week', 'week')}."
        self.speed = 1.0
        self.chance: Chance | None = None
        self.flash = 0.0
        self.crowd = self._make_crowd()
        self.crowd_jump = 0.0
        self.idle = self._idle_sprites()
        self.pitch = self._draw_pitch()
        app.sound.play("whistle")
        app.sound.play("crowd", loops=-1, volume=0.35)

    # --- static art -----------------------------------------------------------
    def _make_crowd(self):
        surf = pygame.Surface((T.CANVAS_W - 2 * T.BORDER, 44))
        surf.fill((40, 40, 50))
        rng = random.Random(7)
        cols = [self.hc.shirt] * 2 + [self.hc.shirt2, self.ac.shirt, T.WHITE, T.LIGHT_GREY, T.GREY, T.BROWN, SKIN]
        for row in range(10):
            for x in range(0, surf.get_width(), 3):
                c = rng.choice(cols)
                surf.fill(c, (x + (row % 2), row * 4 + 3, 2, 2))
        return surf

    def _draw_pitch(self):
        surf = pygame.Surface((T.CANVAS_W, T.CANVAS_H), pygame.SRCALPHA)
        stripes = 14
        for i in range(stripes):
            x0, x1 = 105 * i / stripes, 105 * (i + 1) / stripes
            pts = [project(x0, 0)[:2], project(x1, 0)[:2], project(x1, 68)[:2], project(x0, 68)[:2]]
            pygame.draw.polygon(surf, (60, 150, 60) if i % 2 else (72, 168, 70), pts)
        # surrounding grass
        line = (230, 240, 230)

        def poly(points, closed=True):
            pygame.draw.lines(surf, line, closed, [project(x, y)[:2] for x, y in points], 1)

        poly([(0, 0), (105, 0), (105, 68), (0, 68)])
        poly([(52.5, 0), (52.5, 68)], closed=False)
        circle = [(52.5 + 9.15 * math.cos(a / 24 * 2 * math.pi), 34 + 9.15 * math.sin(a / 24 * 2 * math.pi)) for a in range(24)]
        poly(circle)
        for gx, d in ((0, 1), (105, -1)):
            poly([(gx, 13.85), (gx + d * 16.5, 13.85), (gx + d * 16.5, 54.15), (gx, 54.15)], closed=False)
            poly([(gx, 24.85), (gx + d * 5.5, 24.85), (gx + d * 5.5, 43.15), (gx, 43.15)], closed=False)
            px, py, _ = project(gx + d * 11, 34)
            pygame.draw.rect(surf, line, (px, py, 2, 1))
        return surf

    def _draw_goal(self, surf, gx, d):
        white = (250, 250, 250)
        net = (200, 200, 210)
        back = gx - d * 2.0
        for y in (GOAL_Y1, GOAL_Y2):
            base = project(gx, y)[:2]
            top = project(gx, y, 2.44)[:2]
            pygame.draw.line(surf, white, base, top, 2)
            pygame.draw.line(surf, net, top, project(back, y, 1.8)[:2])
            pygame.draw.line(surf, net, project(back, y, 1.8)[:2], project(back, y)[:2])
        pygame.draw.line(surf, white, project(gx, GOAL_Y1, 2.44)[:2], project(gx, GOAL_Y2, 2.44)[:2], 2)
        pygame.draw.line(surf, net, project(back, GOAL_Y1, 1.8)[:2], project(back, GOAL_Y2, 1.8)[:2])
        for i in range(1, 6):
            yy = lerp(GOAL_Y1, GOAL_Y2, i / 6)
            pygame.draw.line(surf, net, project(gx, yy, 2.44)[:2], project(back, yy, 1.8)[:2])
            pygame.draw.line(surf, net, project(back, yy, 1.8)[:2], project(back, yy)[:2])

    def _idle_sprites(self):
        sprites = []
        for side, xs in (("home", [15, 35, 35, 48]), ("away", [90, 70, 70, 57])):
            for i, x in enumerate(xs):
                sprites.append(Sprite(x, 14 + i * 13, self.kits[side], speed=3))
            gx = 3 if side == "home" else 102
            sprites.append(Sprite(gx, 34, KEEPER_KITS[0 if side == "home" else 1]))
        return sprites

    # --- flow -----------------------------------------------------------------
    def _direction(self, side, minute):
        d = 1 if side == "home" else -1
        return -d if minute > 45 else d

    def _start_event(self):
        e = self.events[self.idx]
        if e.kind == "decision" and e.detail != "offside":
            self._decision(e)
            return
        if e.kind == "injury":
            self.phase = "outcome"
            self.timer = 1.8
            team = self.hc.short if e.side == "home" else self.ac.short
            self.caption, self.caption_col = "INJURY", T.LIGHT_RED
            self.commentary = f"{e.minute}'  {e.player} ({team}) is down injured."
            return
        atk = self.kits[e.side]
        other = "away" if e.side == "home" else "home"
        dfn = self.kits[other]
        keeper = KEEPER_KITS[0 if other == "home" else 1]
        outcome = "goal" if e.kind == "decision" else e.kind  # offside: the ball goes in... then the flag
        self.chance = Chance(self.rng, self._direction(e.side, e.minute), outcome, atk, dfn, keeper)
        team = self.hc.name if e.side == "home" else self.ac.name
        self.commentary = f"{e.minute}'  {team} on the attack..."
        self.caption = ""
        self.phase = "chance"

    def _crowd_reaction(self, against_side: str):
        """Fans boo decisions against their team. The home end is loudest, but when
        you're the away side your travelling support lets the referee know too."""
        if against_side == "home":
            self.app.sound.play("boo", volume=0.9)
            return " The home fans are furious!"
        if self.ac.name == self.g.club_name:
            self.app.sound.play("boo", volume=0.55)
            return " The travelling support are raging!"
        self.app.sound.play("goal", volume=0.25)
        return ""

    def _decision(self, e):
        team = self.hc.name if e.side == "home" else self.ac.name
        m = f"{e.minute}'  "
        caption, text = {
            "penalty": ("NO PENALTY!", f"{e.player} goes down in the box - the referee waves play on!"),
            "free_kick": ("FREE KICK", f"A very soft free kick given against {team}."),
            "booking": ("BOOKED!", f"{e.player} ({team}) is booked for a late challenge."),
            "offside": ("NO GOAL!", f"{e.player} has the ball in the net... but the flag is up! Offside."),
        }[e.detail]
        self.caption = caption
        self.caption_col = T.YELLOW if e.detail == "booking" else T.LIGHT_RED
        self.app.sound.play("whistle")
        self.commentary = m + text + self._crowd_reaction(e.side)
        self.phase = "outcome"
        self.timer = 2.0

    def _finish_chance(self):
        e = self.events[self.idx]
        if e.kind == "decision":  # an offside "goal"
            self._decision(e)
            return
        if e.kind == "goal":
            self.score[0 if e.side == "home" else 1] += 1
            self.caption, self.caption_col = "GOAL!", T.YELLOW
            self.commentary = f"{e.minute}'  {e.player} scores!  {self.hc.short} {self.score[0]}-{self.score[1]} {self.ac.short}"
            self.flash = 2.2
            self.crowd_jump = 2.2
            # the home end makes the most noise; the away fans are fewer
            away_is_mine = e.side == "away" and self.ac.name == self.g.club_name
            self.app.sound.play("goal", volume=1.0 if e.side == "home" else (0.75 if away_is_mine else 0.55))
            self.timer = 2.4
        else:
            words = {"saved": ("SAVED!", f"{e.player}'s shot is saved by {e.keeper}."),
                     "miss": ("WIDE!", f"{e.player} fires wide."),
                     "post": ("OFF THE POST!", f"{e.player} hits the woodwork!")}[e.kind]
            self.caption, self.commentary = words[0], f"{e.minute}'  {words[1]}"
            self.caption_col = T.CYAN
            loud = 1.0 if e.side == "home" else 0.55
            self.app.sound.play("ooh", volume=loud if e.kind != "miss" else loud * 0.8)
            self.timer = 1.6
        self.phase = "outcome"

    def _next(self):
        self.idx += 1
        self.chance = None
        self.caption = ""
        if self.idx < len(self.events):
            self.phase = "clock"
        else:
            self.phase = "clock_ft"

    def _full_time(self):
        self.phase = "fulltime"
        self.minute = 90
        self.score = [self.res.home_goals, self.res.away_goals]
        self.caption, self.caption_col = "FULL TIME", T.WHITE
        r = self.res
        self.commentary = f"Full time: {self.hc.name} {r.home_goals}-{r.away_goals} {self.ac.name}"
        if r.pens:
            self.commentary += f"  ({r.winner} win {r.pens} on penalties)"
        self.chance = None
        self.app.sound.play("whistle")
        if r.winner == r.home and not r.pens:
            self.app.sound.play("goal", volume=0.45)  # home win: applause round the ground
        elif r.winner == r.away and not r.pens:
            self.app.sound.play("boo", volume=0.5)  # home defeat: the faithful aren't happy

    def _leave(self):
        self.app.sound.stop("crowd", fade_ms=600)
        self.app.replace(self.next_scene)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            if self.phase == "fulltime":
                self._leave()
            elif ev.key == pygame.K_ESCAPE:
                self._full_time()
            elif ev.key == pygame.K_SPACE:
                self.speed = 3.0 if self.speed == 1.0 else 1.0
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if self.phase == "fulltime":
                self._leave()
            else:
                self.speed = 3.0 if self.speed == 1.0 else 1.0

    def update(self, dt):
        dt *= self.speed
        self.flash = max(0, self.flash - dt)
        self.crowd_jump = max(0, self.crowd_jump - dt)
        for s in self.idle:
            s.update(dt)
        if self.phase == "kickoff":
            self.timer -= dt
            if self.timer <= 0:
                self.caption = ""
                self.phase = "clock" if self.events else "clock_ft"
        elif self.phase in ("clock", "clock_ft"):
            target = self.events[self.idx].minute if self.phase == "clock" else 90
            self.minute = min(target, self.minute + dt * 60)
            if not self.chance and self.rng.random() < dt * 2:
                s = self.rng.choice(self.idle)
                s.tx = max(2, min(103, s.x + self.rng.uniform(-8, 8)))
                s.ty = max(4, min(64, s.y + self.rng.uniform(-6, 6)))
            if self.minute >= 45 and self.minute - dt * 60 < 45 and target > 45:
                self.commentary = "Half time - the teams change ends."
            if self.minute >= target:
                if self.phase == "clock":
                    self._start_event()
                else:
                    self._full_time()
        elif self.phase == "chance":
            for cue in self.chance.update(dt):
                self.app.sound.play(cue)
            if self.chance.done:
                self._finish_chance()
        elif self.phase == "outcome":
            if self.chance:
                self.chance.update(dt * 0.3)
            self.timer -= dt
            if self.timer <= 0:
                self._next()

    # --- drawing --------------------------------------------------------------
    def draw(self, surf):
        border = T.PALETTE[int(self.flash * 20) % 16] if self.flash > 0 else T.BLACK
        T.frame(surf, border, (40, 110, 40))

        # crowd
        cy = T.BORDER + 44 + (int(math.sin(self.crowd_jump * 25) * 2) if self.crowd_jump else 0)
        surf.blit(self.crowd, (T.BORDER, cy))
        pygame.draw.rect(surf, (60, 60, 70), (T.BORDER, T.BORDER + 88, T.CANVAS_W - 2 * T.BORDER, 8))
        pygame.draw.rect(surf, (230, 230, 230), (T.BORDER, T.BORDER + 96, T.CANVAS_W - 2 * T.BORDER, 2))

        surf.blit(self.pitch, (0, 0))
        self._draw_goal(surf, 0, 1)
        self._draw_goal(surf, 105, -1)

        sprites = self.chance.sprites if self.chance else self.idle
        ball = self.chance.ball if self.chance else None
        items = [(s.y, 0, s) for s in sprites]
        if ball:
            items.append((ball[1], 1, None))
        for _, kind, s in sorted(items, key=lambda i: (i[0], i[1])):
            if kind == 0:
                s.draw(surf)
            else:
                bx, by, bs = project(ball[0], ball[1], 0)
                pygame.draw.ellipse(surf, (30, 90, 30), (bx - 3, by - 1, 6, 3))
                bx, by, bs = project(*ball)
                r = max(3, int(4 * bs))
                pygame.draw.circle(surf, T.WHITE, (int(bx), int(by) - r), r)
                pygame.draw.circle(surf, T.BLACK, (int(bx), int(by) - r), r, 1)
        # the front goal net should overlap the ball when it's in the net
        self._draw_scoreboard(surf)

        if self.caption:
            scale = 4 if self.caption == "GOAL!" else 3
            if self.caption == "GOAL!" and int(self.flash * 8) % 2:
                col = T.WHITE
            else:
                col = self.caption_col
            T.big_text(surf, self.caption, (CX, 170), col, scale=scale, center=True, shadow=T.BLACK)

        # commentary strip
        y = T.CANVAS_H - T.BORDER - 16
        pygame.draw.rect(surf, T.BLACK, (T.BORDER, y, T.CANVAS_W - 2 * T.BORDER, 16))
        used = T.text(surf, self.commentary, (T.BORDER + 6, y + 2), T.WHITE, size=12)
        hint = "SPACE: fast" if self.speed == 1 else "SPACE: normal"
        if self.phase == "fulltime":
            hint = "Press a key"
        hint = f"{hint}  ESC: skip"
        if used + T.font(10).size(hint)[0] + 24 < T.CANVAS_W - 2 * T.BORDER:  # only if there's room
            T.text(surf, hint, (T.CANVAS_W - T.BORDER - 6, y + 3), T.GREY, size=10, right=True)

    def _draw_scoreboard(self, surf):
        x0, y0, w = T.BORDER, T.BORDER, T.CANVAS_W - 2 * T.BORDER
        pygame.draw.rect(surf, T.BLACK, (x0, y0, w, 42))
        T.kit_swatch(surf, x0 + 10, y0 + 8, self.kits["home"], 14, 18)
        T.kit_swatch(surf, x0 + w - 24, y0 + 8, self.kits["away"], 14, 18)
        T.text(surf, self.hc.name.upper(), (x0 + 32, y0 + 6), T.YELLOW if self.hc.name == self.g.club_name else T.WHITE, bold=True)
        T.text(surf, self.ac.name.upper(), (x0 + w - 32, y0 + 6), T.YELLOW if self.ac.name == self.g.club_name else T.WHITE, bold=True, right=True)
        T.big_text(surf, f"{self.score[0]} - {self.score[1]}", (CX, y0 + 2), T.WHITE, center=True, scale=2)
        comp = self.comp if len(self.comp) <= 48 else self.comp.split(" (")[0]
        T.text(surf, f"{int(self.minute)}'", (x0 + 32, y0 + 24), T.CYAN)
        T.text(surf, comp, (CX, y0 + 30), T.LIGHT_GREY, size=10, center=True)
