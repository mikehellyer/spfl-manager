"""The game state: clubs, squads, fixtures, tables, cup, finances and the weekly loop."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from . import cup as cupmod
from . import data, stats
from . import league_cup as lcup
from . import playoffs as po
from .database import START_YEAR, SquadDB
from .fixtures import cup_draw, league_schedule
from .match import MatchResult, simulate_match
from .match import shootout as run_shootout
from .models import FORM_MAX, Club, Player, round_money
from .names import FIRST_NAMES, SURNAMES

SQUAD_TEMPLATE = ["GK", "GK"] + ["DEF"] * 5 + ["MID"] * 5 + ["ATT"] * 4
FORMATION_442 = {"GK": 1, "DEF": 4, "MID": 4, "ATT": 2}
MAX_SQUAD = 32
MIN_SQUAD = 13
SAVE_VERSION = 2
YOUTH_TARGET = 18  # at the end of each season clubs promote youngsters up to this squad size
# form: how a match went for a player (win/lose, goals, clean sheets, red cards), scaled onto
# -FORM_MAX..FORM_MAX and blended into their form. Players left out drift back towards 0.
FORM_RESULT = 3
FORM_PENS_RESULT = 1  # a shoot-out is closer to a draw than a win or a defeat
FORM_GOAL = 3
FORM_CLEAN_SHEET = 2  # keepers and defenders; they lose as much after conceding 3 or more
FORM_RED_CARD = -4
FORM_SCALE = 1.5
FORM_NOISE = 2.0  # a good or a bad day that the scoreline doesn't show
FORM_KEEP = 0.65  # share of the old form kept after each match


@dataclass
class WeekReport:
    label: str
    player_result: MatchResult | None = None
    results: list = field(default_factory=list)  # MatchResults for the player's competition
    news: list = field(default_factory=list)
    finance: dict = field(default_factory=dict)
    player_comp: str = ""  # competition label for the manager's match
    venue: str = ""  # set for neutral-venue matches (cup semi-finals and final)
    cup_rounds: list = field(default_factory=list)  # [(round label, [MatchResult, ...])]
    season_summary: dict | None = None


LEAGUE_WEEKS = 38  # the Premiership's 33 games + 5 after the split
LOWER_LEAGUE_WEEKS = 36
SPLIT_AFTER = 33


def build_calendar() -> list[list]:
    """Events: ["lcup_group", matchday], ["league", round], ["cup", round], ["lcup", round],
    ["playoff", week].

    The League Cup group stage is pre-season (July). The lower leagues finish two
    weeks before the Premiership, so their play-offs start while the Premiership
    plays its last two rounds: those weeks are ["league", round, playoff_week].
    """
    cal = [["lcup_group", md] for md in range(lcup.MATCHDAYS)]
    for r in range(LEAGUE_WEEKS):
        ev = ["league", r]
        if r >= LOWER_LEAGUE_WEEKS:
            ev.append(r - LOWER_LEAGUE_WEEKS)
        cal.append(ev)
        for idx in cupmod.event_rounds(r + 1):  # Scottish Cup weekends with SPFL clubs
            cal.append(["cup", idx])
        for idx in lcup.event_rounds(r + 1):  # League Cup knock-out rounds
            cal.append(["lcup", idx])
    for w in range(LEAGUE_WEEKS - LOWER_LEAGUE_WEEKS, po.PLAYOFF_WEEKS):
        cal.append(["playoff", w])
    return cal


def calendar_v10() -> list[list]:
    """The v0.10 calendar (no League Cup), for migrating saves.
    Events: ["league", round], ["cup", round], ["playoff", week].

    The lower leagues finish two weeks before the Premiership, so their
    play-offs start while the Premiership plays its last two rounds:
    those weeks are ["league", round, playoff_week].
    """
    cal = []
    for r in range(LEAGUE_WEEKS):
        ev = ["league", r]
        if r >= LOWER_LEAGUE_WEEKS:
            ev.append(r - LOWER_LEAGUE_WEEKS)
        cal.append(ev)
        for idx in cupmod.event_rounds(r + 1):  # cup weekends with SPFL clubs
            cal.append(["cup", idx])
    for w in range(LEAGUE_WEEKS - LOWER_LEAGUE_WEEKS, po.PLAYOFF_WEEKS):
        cal.append(["playoff", w])
    return cal


def legacy_calendar() -> list[list]:
    """The calendar used by saves from v0.6-v0.9 (six cup rounds), for migrating them."""
    old_cup_after = {4: 0, 10: 1, 16: 2, 22: 3, 28: 4, 33: 5}
    cal = []
    for r in range(LEAGUE_WEEKS):
        ev = ["league", r]
        if r >= LOWER_LEAGUE_WEEKS:
            ev.append(r - LOWER_LEAGUE_WEEKS)
        cal.append(ev)
        if r + 1 in old_cup_after:
            cal.append(["cup", old_cup_after[r + 1]])
    for w in range(LEAGUE_WEEKS - LOWER_LEAGUE_WEEKS, po.PLAYOFF_WEEKS):
        cal.append(["playoff", w])
    return cal


def empty_row() -> dict:
    return {"P": 0, "W": 0, "D": 0, "L": 0, "F": 0, "A": 0, "Pts": 0, "form": ""}


class Game:
    def __init__(self):
        self.rng = random.Random()
        self.manager = "Manager"
        self.club_name = ""
        self.season = START_YEAR
        self.week = 0
        self.calendar = build_calendar()
        self.clubs: dict[str, Club] = {}
        self.players: dict[int, Player] = {}
        self.divisions: list[list[str]] = [[] for _ in data.DIVISIONS]
        self.fixtures: list = []
        self.tables: dict[str, dict] = {}
        self.cup: dict = {}
        self.balance = 0
        self.loan = 0
        self.market: list = []  # [[player_id, asking_price]]
        self.news: list[str] = []
        self.history: list[dict] = []
        self.records: dict = {}  # the manager's biggest win, heaviest defeat, best scorer
        self.player_results: list = []  # the manager's own results this season
        self.next_id = 1
        self.board_warnings = 0
        self.sacked = False
        self.last_finance: dict = {}
        self.playoffs: dict = {}
        self.split: dict = {}  # Premiership split: {"top": [...6], "bottom": [...6]}
        self.league_cup: dict = {}
        self.europe: list[str] = list(lcup.REAL_2026_EUROPE)  # clubs in Europe this season
        self.prev_order: list[str] = []  # last season's final positions, all divisions (for seeding)
        self.pyramid_champions: list[str] = []  # last pyramid play-off: [Highland champs, Lowland champs]
        self.game_over_reason = ""
        # clubs outside the SPFL who can win the pyramid play-off (ex-SPFL clubs join it)
        self.non_league: list[dict] = [
            {"league": lg, **{k: list(v) if isinstance(v, tuple) else v for k, v in c._asdict().items()}}
            for lg, c in data.PYRAMID_CLUBS
        ]

    # ------------------------------------------------------------------ setup
    @classmethod
    def new(cls, manager: str, club_name: str, seed: int | None = None, db: SquadDB | None = None) -> Game:
        g = cls()
        g.rng = random.Random(seed)
        g.manager = manager or "Manager"
        db = db or SquadDB.load()
        for div, clubs in enumerate(data.CLUBS):
            for info in clubs:
                rating = db.rating(info.name)
                club = Club(
                    info.name,
                    info.short,
                    div,
                    info.shirt,
                    info.shorts,
                    info.stadium,
                    info.capacity,
                    rating,
                    pattern=info.pattern,
                    shirt2=info.shirt2,
                )
                g.clubs[info.name] = club
                g.divisions[div].append(info.name)
                squad = db.clubs.get(info.name)
                if squad:
                    for rec in squad:
                        g._real_player(info.name, rec, db)
                    g._top_up_squad(info.name)
                else:
                    for pos in SQUAD_TEMPLATE:
                        g._new_player(info.name, pos, rating)
        g.club_name = club_name
        club = g.club
        g.balance = round_money(sum(p.wage for p in g.squad(club_name)) * 12)
        for c in g.clubs.values():
            c.selected = g.auto_pick(c.name)
        g._start_season()
        g.news.append(
            f"The board of {club.name} welcome {g.manager} as the new manager. "
            f"Good luck in the {data.DIVISION_FULL[club.division]}!"
        )
        return g

    def _new_player(self, club: str, pos: str, rating: int, age: int | None = None) -> Player:
        skill = max(8, min(99, int(self.rng.gauss(rating, 6))))
        if age is None:
            age = self.rng.randint(17, 34)
        p = Player(
            id=self.next_id,
            name=f"{self.rng.choice(FIRST_NAMES)[0]}. {self.rng.choice(SURNAMES)}",
            pos=pos,
            skill=skill,
            age=age,
            club=club,
        )
        self.next_id += 1
        self.players[p.id] = p
        return p

    def _real_player(self, club: str, rec: dict, db: SquadDB) -> Player:
        skill, age, _, _ = db.stats(club, rec, self.season)
        p = Player(id=self.next_id, name=rec["name"], pos=rec["pos"], skill=skill, age=age, club=club)
        self.next_id += 1
        self.players[p.id] = p
        return p

    def _start_season(self):
        self.week = 0
        self.fixtures = []
        for teams in self.divisions:
            cycles = data.LEAGUE_CYCLES[len(teams)]
            self.fixtures.append(league_schedule(teams, cycles, self.rng))
        self.tables = {name: empty_row() for name in self.clubs}
        self.calendar = build_calendar()
        self.cup = cupmod.new_cup()
        self._cup_draw()
        self.player_results = []
        self.playoffs = {}
        self.split = {}
        self._new_league_cup()
        for p in self.players.values():
            p.goals = p.apps = p.form = 0
        self._refresh_market()

    # ------------------------------------------------------------ properties
    @property
    def club(self) -> Club:
        return self.clubs[self.club_name]

    @property
    def season_label(self) -> str:
        return f"{self.season}/{str(self.season + 1)[-2:]}"

    @property
    def season_over(self) -> bool:
        return self.week >= len(self.calendar)

    def squad(self, club: str) -> list[Player]:
        order = {pos: i for i, pos in enumerate(("GK", "DEF", "MID", "ATT"))}
        return sorted(
            (p for p in self.players.values() if p.club == club),
            key=lambda p: (order[p.pos], -p.skill),
        )

    def selected_players(self, club: str) -> list[Player]:
        return [self.players[i] for i in self.clubs[club].selected if i in self.players]

    def wage_bill(self, club: str | None = None) -> int:
        return sum(p.wage for p in self.squad(club or self.club_name))

    def table(self, div: int) -> list[tuple[str, dict]]:
        rows = [(name, self.tables[name]) for name in self.divisions[div]]
        top = set(self.split.get("top", [])) if div == 0 else set()

        def key(r):
            half = 0 if (not top or r[0] in top) else 1  # after the split, the halves never cross
            return (half, -r[1]["Pts"], -(r[1]["F"] - r[1]["A"]), -r[1]["F"], r[0])

        rows.sort(key=key)
        return rows

    def _event(self, idx: int | None = None) -> tuple[str, int, int | None]:
        """(kind, round, play-off week or None) for a calendar slot."""
        ev = self.calendar[self.week if idx is None else idx]
        if ev[0] == "playoff":
            return "playoff", ev[1], ev[1]
        return ev[0], ev[1], ev[2] if len(ev) > 2 else None

    def playoff_week(self, idx: int | None = None) -> int | None:
        idx = self.week if idx is None else idx
        if idx >= len(self.calendar):
            return None
        return self._event(idx)[2]

    def _make_split(self):
        """After 33 games the Premiership splits into a top six and a bottom six.

        Each club plays the other five in its half once more. The home side is
        the club that hosted that fixture less often before the split.
        """
        from collections import Counter

        from .fixtures import round_robin

        order = [n for n, _ in self.table(0)]
        top, bottom = order[:6], order[6:]
        hosted = Counter((h, a) for rnd in self.fixtures[0] for h, a in rnd)
        rounds: list[list] = [[] for _ in range(5)]
        for half in (top, bottom):
            for i, rnd in enumerate(round_robin(half)):
                for h, a in rnd:
                    if hosted[(h, a)] > hosted[(a, h)]:
                        h, a = a, h
                    rounds[i].append([h, a])
        self.fixtures[0] = self.fixtures[0][:SPLIT_AFTER] + rounds
        self.split = {"top": top, "bottom": bottom}
        self.news.insert(0, "The Premiership has split! Top six: " + ", ".join(top) + ".")

    def position(self, club: str | None = None) -> int:
        """League position, or 0 for a club outside the SPFL (a pyramid play-off challenger)."""
        club = club or self.club_name
        div = self.clubs[club].division
        if not 0 <= div < len(self.divisions) or club not in self.divisions[div]:
            return 0
        return [n for n, _ in self.table(div)].index(club) + 1

    def event_label(self, idx: int | None = None) -> str:
        idx = self.week if idx is None else idx
        if idx >= len(self.calendar):
            return "Season over"
        kind, n, pw = self._event(idx)
        if kind == "league":
            if pw is not None and n >= len(self.fixtures[self.club.division]):
                return f"Play-offs Week {pw + 1}"  # our league is finished; the Premiership plays on
            return f"League Week {n + 1}"
        if kind == "playoff":
            return f"Play-offs Week {n + 1}"
        if kind == "lcup_group":
            return lcup.label_group(n)
        if kind == "lcup":
            return lcup.label_round(n)
        return cupmod.label(n)

    def next_fixture(self) -> tuple[str, str, str] | None:
        """(home, away, competition label) for the manager's game this week, or None."""
        if self.season_over:
            return None
        kind, n, pw = self._event()
        if kind == "league":
            rounds = self.fixtures[self.club.division]
            if n < len(rounds):
                for h, a in rounds[n]:
                    if self.club_name in (h, a):
                        return h, a, data.DIVISION_FULL[self.club.division]
            elif self.club.division == 0 and n >= SPLIT_AFTER and not self.split:
                self._make_split()
                return self.next_fixture()
        if kind == "cup":
            for h, a in self.cup["ties"]:
                if self.club_name in (h, a):
                    return h, a, cupmod.label(n)
            return None
        if kind in ("lcup_group", "lcup"):
            st = self.league_cup
            games = st["fixtures"][n] if kind == "lcup_group" else st.get("ties", [])
            if kind == "lcup" and st.get("round") != n:
                games = []
            for h, a in games:
                if self.club_name in (h, a):
                    return h, a, lcup.label_group(n) if kind == "lcup_group" else lcup.label_round(n)
            return None
        if pw is not None:
            self._ensure_playoffs()
            for tie, leg, h, a in po.fixtures(self.playoffs, pw):
                if self.club_name in (h, a):
                    return h, a, po.leg_label(tie, leg, self._short)
        return None

    def _fill_premiership_playoff(self):
        """Once the Premiership has finished, its 11th-placed club enters the play-off final."""
        tie = po.get(self.playoffs, "prem_f")
        if tie and tie["b"] == "?":
            eleventh = self.table(0)[10][0]
            tie["b"] = tie["stay"] = eleventh

    def _short(self, name: str) -> str:
        club = self.clubs.get(name)
        return club.short if club else name[:3].upper()

    def in_playoffs(self) -> bool:
        """Is the manager's club still involved in a play-off tie?"""
        return any(
            self.club_name in (t["a"], t["b"]) and not t["winner"] for t in self.playoffs.get("ties", [])
        ) or any(
            (t["a"] == "?" or t["b"] == "?") and self._could_reach(t) for t in self.playoffs.get("ties", [])
        )

    def _could_reach(self, tie: dict) -> bool:
        for src in (tie["a_from"], tie["b_from"]):
            t = po.get(self.playoffs, src) if src else None
            if t and not t["winner"] and self.club_name in (t["a"], t["b"]):
                return True
        return False

    def _ensure_playoffs(self):
        """Set up the play-offs once every league has finished."""
        if self.playoffs:
            return
        finals = [[n for n, _ in self.table(d)] for d in range(4)]
        finals[0] = None  # the Premiership is still playing - its 11th place joins the final later
        # the pyramid play-off: Highland League champions v Lowland League champions
        spfl = {c for div in self.divisions for c in div}
        pool = [c for c in self.non_league if c["name"] not in spfl]
        highland = [c for c in pool if c["league"] == "HL"] or pool
        lowland = [c for c in pool if c["league"] == "LL" and c not in highland[:1]] or pool
        hl = self.rng.choice(highland)
        ll = self.rng.choice([c for c in lowland if c is not hl] or [hl])
        self.pyramid_champions = [hl["name"], ll["name"]]
        entrant = hl if self.rng.random() < 0.5 + (hl["rating"] - ll["rating"]) / 100 else ll
        other = ll if entrant is hl else hl
        entrant, other = data.ClubInfo(**{k: v for k, v in entrant.items() if k != "league"}), other["name"]
        if entrant.name in self.clubs:  # already in the game (e.g. a cup run) - keep that squad
            self.playoffs = po.create(finals, entrant.name)
            self.news.insert(0, f"Pyramid play-off: {entrant.name} beat {other} for a crack at League Two.")
            return
        club = Club(
            entrant.name,
            entrant.short,
            4,
            tuple(entrant.shirt),
            tuple(entrant.shorts),
            entrant.stadium,
            entrant.capacity,
            entrant.rating,
            pattern=entrant.pattern,
            shirt2=tuple(entrant.shirt2),
        )
        self.clubs[club.name] = club
        for pos in SQUAD_TEMPLATE:
            self._new_player(club.name, pos, club.rating)
        club.selected = self.auto_pick(club.name)
        self.playoffs = po.create(finals, club.name)
        self.news.insert(
            0,
            f"Pyramid play-off: {entrant.name} beat {other} and will play "
            f"{finals[3][9]} for a place in League Two.",
        )

    def league_fixture_list(self) -> list[tuple[int, str, str]]:
        out = []
        for r, rnd in enumerate(self.fixtures[self.club.division]):
            for h, a in rnd:
                if self.club_name in (h, a):
                    out.append((r, h, a))
        return out

    # ------------------------------------------------------------ selection
    def auto_pick(self, club: str) -> list[int]:
        avail = [p for p in self.squad(club) if p.available]
        chosen: list[Player] = []
        for pos, n in FORMATION_442.items():
            best = sorted((p for p in avail if p.pos == pos), key=lambda p: -p.effective)
            chosen += best[:n]
        rest = sorted((p for p in avail if p not in chosen and p.pos != "GK"), key=lambda p: -p.effective)
        while len(chosen) < 11 and rest:
            chosen.append(rest.pop(0))
        return [p.id for p in chosen]

    def toggle_selection(self, player_id: int) -> str:
        sel = self.club.selected
        p = self.players[player_id]
        if player_id in sel:
            sel.remove(player_id)
            return ""
        if not p.available:
            return f"{p.name} is suspended." if p.suspended else f"{p.name} is injured."
        if len(sel) >= 11:
            return "You already have 11 players picked."
        sel.append(player_id)
        return ""

    def _validate_selection(self, club: str) -> list[str]:
        c = self.clubs[club]
        notes = []
        for pid in list(c.selected):
            p = self.players.get(pid)
            if p is None or p.club != club or not p.available:
                c.selected.remove(pid)
                if p is not None and p.club == club:
                    why = "suspended" if p.suspended else "injured"
                    notes.append(f"{p.name} is {why} and was dropped.")
        if len(c.selected) < 11:
            auto = [pid for pid in self.auto_pick(club) if pid not in c.selected]
            added = auto[: 11 - len(c.selected)]
            c.selected += added
            if club == self.club_name and added:
                names = ", ".join(self.players[i].name for i in added)
                notes.append(f"Short of players - {names} drafted in.")
        return notes

    # ------------------------------------------------------------ the week
    def play_week(self) -> WeekReport:
        if self.season_over:
            raise RuntimeError("Season is over")
        kind, n, pw = self._event()
        report = WeekReport(self.event_label())
        self._release_knocked_out()
        if kind == "league" and n >= SPLIT_AFTER and not self.split and len(self.fixtures[0]) <= SPLIT_AFTER:
            self._make_split()
            report.news.append(self.news[0])

        for p in self.players.values():
            if p.injury:
                p.injury -= 1

        report.news += self._validate_selection(self.club_name)
        for name in self.clubs:
            if name != self.club_name:
                self.clubs[name].selected = self.auto_pick(name)

        played: set[int] = set()
        all_results: list[MatchResult] = []
        home_game = False
        if kind == "league":
            for div, rounds in enumerate(self.fixtures):
                if n >= len(rounds):
                    continue
                for h, a in rounds[n]:
                    res = self._play(h, a, cup=False)
                    all_results.append(res)
                    self._apply_league(res)
                    played.update(res.home_xi + res.away_xi)
                    if div == self.club.division:
                        report.results.append(res)
                    if self.club_name in (h, a):
                        report.player_result = res
                        home_game = h == self.club_name
        elif kind == "cup":
            home_game = self._play_cup_round(n, report, all_results, played)
        elif kind == "lcup_group":
            home_game = self._play_league_cup_matchday(n, report, all_results, played)
        elif kind == "lcup":
            home_game = self._play_league_cup_round(n, report, all_results, played)
        if kind == "league":
            # early non-league rounds are played on the same weekend
            for idx in cupmod.attached_rounds(n + 1):
                self._play_cup_round(idx, report, all_results, played)

        if pw is not None:
            self._ensure_playoffs()
            if pw >= LEAGUE_WEEKS - LOWER_LEAGUE_WEEKS:
                self._fill_premiership_playoff()
            for tie, leg, h, a in po.fixtures(self.playoffs, pw):
                res = self._play(h, a, cup=False)
                all_results.append(res)
                played.update(res.home_xi + res.away_xi)
                report.results.append(res)
                if self.club_name in (h, a):
                    report.player_result = res
                    report.player_comp = po.leg_label(tie, leg, self._short)
                    home_game = h == self.club_name

                def shootout(t=tie, res=res):
                    # level on aggregate: penalties at the end of the second leg (kept for highlights)
                    home_pens, away_pens, res.shootout = run_shootout(
                        self.selected_players(res.home), self.selected_players(res.away), self.rng
                    )
                    return (home_pens, away_pens) if t["a"] == res.home else (away_pens, home_pens)

                line = po.record_leg(self.playoffs, tie, res.home_goals, res.away_goals, shootout)
                if line:
                    report.news.append(line)
        if report.player_result:
            if not report.player_comp:
                report.player_comp = (
                    data.DIVISION_FULL[self.club.division] if kind == "league" else report.label
                )
            self._record_player_result(report.player_result)

        self._fitness_and_injuries(played, all_results, report)
        report.finance = self._weekly_finances(home_game, report.player_result)
        self._board_check(report)
        self._refresh_market()

        self.week += 1
        if self.season_over:
            report.season_summary = self._end_season()
        self.news = report.news + self.news
        self.news = self.news[:40]
        return report

    # scottish cup -----------------------------------------------------------
    def cup_status(self) -> str:
        cup = self.cup
        if cup.get("winner") == self.club_name:
            return "Winners!"
        if cup.get("out"):
            return "Out"
        if cup.get("winner"):
            return "Out"
        enters = cupmod.entry_round(self.club.division)
        if cup.get("round", 0) <= enters and not self._in_cup_draw():
            return f"Enter in {cupmod.round_name(enters)}"
        return "Still in"

    def cup_next_label(self) -> str:
        cup = self.cup
        if cup.get("round", 0) >= len(data.CUP_ROUNDS):
            return ""
        return f"{cupmod.label(cup['round'])} ({len(cup.get('ties', []))} ties)"

    @staticmethod
    def cup_neutral(comp_label: str) -> bool:
        """Is this competition label a neutral-venue cup tie (semi-final or final)?"""
        return any(comp_label == cupmod.label(i) for i in data.NEUTRAL_VENUE_ROUNDS) or any(
            comp_label == lcup.label_round(i) for i in lcup.NEUTRAL_ROUNDS
        )

    # league cup -------------------------------------------------------------
    def _new_league_cup(self):
        spfl = [c for div in self.divisions for c in div]
        real = [t for g in lcup.REAL_2026_GROUPS for t in g]
        use_real = self.season == START_YEAR and all(
            t in spfl or t in lcup.REAL_2026_NON_LEAGUE for t in real
        )
        if use_real:
            groups, europe, non_league = (
                lcup.REAL_2026_GROUPS,
                lcup.REAL_2026_EUROPE,
                lcup.REAL_2026_NON_LEAGUE,
            )
        else:
            europe = [c for c in self.europe if c in spfl][:5]
            for c in spfl:  # top up if a European club has left the SPFL (can't really happen)
                if len(europe) < 5 and c not in europe:
                    europe.append(c)
            non_league = self._league_cup_non_league_entrants()
            rank = {c: i for i, c in enumerate(self.prev_order)}
            ranked = sorted((c for c in spfl if c not in europe), key=lambda c: rank.get(c, 999))
            groups = lcup.draw_groups(ranked + non_league, self.rng)
        ratings = {n: data.NON_LEAGUE_RATINGS.get(n, 28) for n in non_league}
        self.league_cup = lcup.new_competition([list(g) for g in groups], europe, ratings, self.rng)
        for n in non_league:
            self._ensure_non_league_club(n, ratings[n])

    def _league_cup_non_league_entrants(self) -> list[str]:
        """Highland League champions and runners-up, Lowland League champions.

        The champions are last season's pyramid play-off clubs (unless one has just been
        promoted into the SPFL). Clubs that were in the SPFL last season don't qualify.
        """
        spfl = {c for div in self.divisions for c in div}
        last_season = set(self.prev_order)
        pool = [c for c in self.non_league if c["name"] not in spfl and c["name"] not in last_season]
        league_of = {c["name"]: c["league"] for c in pool}
        picks = [n for n in self.pyramid_champions if n in league_of]
        jitter = {c["name"]: c["rating"] + self.rng.uniform(0, 3) for c in pool}
        for want in ("HL", "HL", "LL", "HL", "LL"):  # fill the gaps, Highland first
            if len(picks) >= 3:
                break
            have = sum(1 for n in picks if league_of[n] == want)
            if want == "HL" and have >= 2 or want == "LL" and have >= 1:
                continue
            best = sorted(
                (n for n in league_of if league_of[n] == want and n not in picks), key=lambda n: -jitter[n]
            )
            if best:
                picks.append(best[0])
        for n in sorted(league_of, key=lambda n: -jitter[n]):  # small pool: anyone left
            if len(picks) >= 3:
                break
            if n not in picks:
                picks.append(n)
        return picks

    def _play_league_cup_matchday(self, md: int, report: WeekReport, all_results: list, played: set) -> bool:
        st = self.league_cup
        if st.get("stage") != "groups" or st.get("matchday") != md:
            return False
        home_game = False
        results = []
        for h, a in st["fixtures"][md]:
            self._ensure_non_league_club(h)
            self._ensure_non_league_club(a)
            res = self._play(h, a, cup=True)  # a draw goes straight to penalties
            lcup.record_group_result(st, h, a, res.home_goals, res.away_goals, res.pens)
            all_results.append(res)
            played.update(res.home_xi + res.away_xi)
            results.append(res)
            if self.club_name in (h, a):
                report.player_result = res
                report.player_comp = lcup.label_group(md)
                home_game = h == self.club_name
        report.cup_rounds.append((lcup.label_group(md), results))
        st["matchday"] = md + 1
        if md == lcup.MATCHDAYS - 1:
            qualifiers, seeded = lcup.finish_groups(st, self.rng)
            report.news.append(f"{lcup.NAME} group stage over: " + ", ".join(qualifiers) + " go through.")
            group = self.league_cup_group()
            if group is not None:
                pos = lcup.standings(st, group).index(self.club_name) + 1
                through = self.club_name in qualifiers
                report.news.append(
                    f"{self.club_name} finish {pos}{'st' if pos == 1 else 'nd' if pos == 2 else 'th'} in "
                    f"Group {lcup.GROUP_NAMES[group]} - "
                    + ("through to the Second Round!" if through else "out of the League Cup.")
                )
                st["out"] = not through
        return home_game

    def _play_league_cup_round(self, idx: int, report: WeekReport, all_results: list, played: set) -> bool:
        st = self.league_cup
        if st.get("stage") != "knockout" or st.get("round") != idx or not st.get("ties"):
            return False
        neutral = idx in lcup.NEUTRAL_ROUNDS
        home_game = False
        results, winners = [], []
        for h, a in st["ties"]:
            self._ensure_non_league_club(h)
            self._ensure_non_league_club(a)
            res = self._play(h, a, cup=True)
            all_results.append(res)
            played.update(res.home_xi + res.away_xi)
            results.append(res)
            winners.append(res.winner)
            if self.club_name in (h, a):
                report.player_result = res
                report.player_comp = lcup.label_round(idx)
                if neutral:
                    report.venue = data.NEUTRAL_VENUE
                home_game = h == self.club_name and not neutral
                if res.winner == self.club_name:
                    prize = lcup.PRIZE[idx]
                    self.balance += prize
                    report.news.append(
                        (
                            "LEAGUE CUP WINNERS!"
                            if idx == len(lcup.KO_ROUNDS) - 1
                            else f"Through in the {lcup.NAME}!"
                        )
                        + f" £{prize:,} prize money."
                    )
                else:
                    st["out"] = True
                    report.news.append(f"Knocked out of the {lcup.NAME}.")
        report.cup_rounds.append((lcup.label_round(idx), results))
        st["round"] = idx + 1
        if idx == len(lcup.KO_ROUNDS) - 1:
            st["winner"] = winners[0]
            st["ties"] = []
            st["stage"] = "done"
            report.news.append(f"{winners[0]} win the {lcup.NAME}!")
        else:
            st["ties"] = cup_draw(winners, self.rng)
        return home_game

    def league_cup_group(self) -> int | None:
        for i, g in enumerate(self.league_cup.get("groups", [])):
            if self.club_name in g:
                return i
        return None

    def league_cup_status(self) -> str:
        st = self.league_cup
        if not st:
            return "-"
        if st.get("winner") == self.club_name:
            return "Winners!"
        if st.get("out") or st.get("stage") == "done":
            return "Out"
        if st["stage"] == "groups":
            g = self.league_cup_group()
            if g is None:
                return "Enter in Second Round"  # a European club
            if st["tables"][self.club_name]["P"] == 0:
                return f"Group {lcup.GROUP_NAMES[g]}"
            pos = lcup.standings(st, g).index(self.club_name) + 1
            return f"Group {lcup.GROUP_NAMES[g]}: {pos}{'st' if pos == 1 else 'nd' if pos == 2 else 'rd' if pos == 3 else 'th'}"
        return f"In the {lcup.KO_ROUNDS[st['round']][0]}"

    def league_cup_next_label(self) -> str:
        st = self.league_cup
        if st.get("stage") == "groups":
            return lcup.label_group(st["matchday"])
        if st.get("stage") == "knockout":
            return f"{lcup.label_round(st['round'])} ({len(st['ties'])} ties)"
        return ""

    def _in_cup_draw(self) -> bool:
        cup = self.cup
        return self.club_name in cup.get("byes", []) or any(self.club_name in t for t in cup.get("ties", []))

    def _ensure_non_league_club(self, name: str, rating: int | None = None) -> Club:
        """Give a non-league cup side a squad when they draw an SPFL club."""
        if name in self.clubs:
            return self.clubs[name]
        if rating is None:
            rating = self.cup.get("ratings", {}).get(name) or self.league_cup.get("ratings", {}).get(name, 27)
        known = next((c for _, c in data.PYRAMID_CLUBS if c.name == name), None)
        former = next((c for c in self.non_league if c["name"] == name), None)
        if known:
            kit = (known.shirt, known.shorts, known.pattern, known.shirt2)
            stadium, cap = known.stadium, known.capacity
        elif former:
            kit = (
                tuple(former["shirt"]),
                tuple(former["shorts"]),
                former["pattern"],
                tuple(former["shirt2"]),
            )
            stadium, cap = former["stadium"], former["capacity"]
        else:
            kit = cupmod.kit_for(name)
            stadium, cap = f"{name}'s ground", 2000
        club = Club(
            name,
            cupmod.short_code(name),
            4,
            kit[0],
            kit[1],
            stadium,
            cap,
            rating,
            pattern=kit[2],
            shirt2=kit[3],
        )
        self.clubs[name] = club
        for pos in SQUAD_TEMPLATE:
            self._new_player(name, pos, rating)
        club.selected = self.auto_pick(name)
        return club

    def _play_cup_round(self, idx: int, report: WeekReport, all_results: list, played: set) -> bool:
        """Play every tie in cup round `idx`. Returns True if the manager's club played at home."""
        cup = self.cup
        if cup.get("round") != idx or not cup.get("ties"):
            return False
        neutral = idx in data.NEUTRAL_VENUE_ROUNDS
        home_game = False
        results, winners = [], []
        for h, a in cup["ties"]:
            if h in self.clubs or a in self.clubs:  # an SPFL club is involved: a proper match
                self._ensure_non_league_club(h)
                self._ensure_non_league_club(a)
                res = self._play(h, a, cup=True)
                all_results.append(res)
                played.update(res.home_xi + res.away_xi)
            else:  # two non-league sides
                ratings = cup["ratings"]
                res = cupmod.quick_result(h, a, ratings.get(h, 25), ratings.get(a, 25), self.rng)
            results.append(res)
            winners.append(res.winner)
            if self.club_name in (h, a):
                report.player_result = res
                report.player_comp = cupmod.label(idx)
                if neutral:
                    report.venue = data.NEUTRAL_VENUE
                home_game = h == self.club_name and not neutral
                if res.winner == self.club_name:
                    prize = data.CUP_PRIZE[idx]
                    self.balance += prize
                    if idx == len(data.CUP_ROUNDS) - 1:
                        report.news.append(f"SCOTTISH CUP WINNERS! £{prize:,} prize money.")
                    else:
                        report.news.append(f"Through in the {data.CUP_NAME}! £{prize:,} prize money.")
                else:
                    cup["out"] = True
                    report.news.append(f"Knocked out of the {data.CUP_NAME}.")
        report.cup_rounds.append((cupmod.label(idx), results))

        cup["remaining"] = winners + cup["byes"]
        cup["byes"], cup["ties"] = [], []
        cup["round"] = idx + 1
        still_in = set(cup["remaining"])
        cup["ratings"] = {k: v for k, v in cup["ratings"].items() if k in still_in}
        if idx == len(data.CUP_ROUNDS) - 1:
            cup["winner"] = winners[0]
            report.news.append(f"{winners[0]} win the {data.CUP_NAME}!")
        else:
            if idx < data.FIRST_SPFL_ROUND:
                report.news.append(f"{cupmod.label(idx)}: {len(results)} ties played.")
            self._cup_draw()
            if cup["round"] == cupmod.entry_round(self.club.division) and self._in_cup_draw():
                opp = next(
                    (t[0] if t[1] == self.club_name else t[1] for t in cup["ties"] if self.club_name in t), ""
                )
                if opp:
                    report.news.append(f"{data.CUP_NAME} draw: {self.club_name} will play {opp}.")
        return home_game

    def _cup_draw(self):
        """Make the next draw, and give any non-league side drawn against an SPFL club a
        squad straight away (so the fixture, pre-match and highlights screens can show them)."""
        cupmod.make_draw(self, self.cup, self.rng)
        spfl = {c for div in self.divisions for c in div}
        for h, a in self.cup["ties"]:
            if h in spfl or a in spfl:
                self._ensure_non_league_club(h)
                self._ensure_non_league_club(a)

    def _release_knocked_out(self):
        """Non-league sides who are out of the cup go home (with their squads). Done at the
        start of the next week so this week's result and highlights screens can still show them."""
        cup = self.cup
        alive = set(cup.get("remaining", [])) | set(cup.get("byes", []))
        alive |= {t for tie in cup.get("ties", []) for t in tie}
        alive |= lcup.alive(self.league_cup)
        for name in [n for n, c in self.clubs.items() if c.division == 4]:
            if name not in alive and name != self.playoffs.get("entrant"):
                self._remove_club(name)

    def _migrate_old_save(self, legacy_sc: bool):
        """Move a save from an older version onto the current calendar and cups.

        v0.10 saves had no League Cup; saves before v0.10 also had a simpler six-round
        Scottish Cup. Keep the place in the season, then play any cup rounds that are
        now in the past (their results go into the news).
        """
        old_cal = legacy_calendar() if legacy_sc else calendar_v10()
        old_ev = old_cal[self.week] if self.week < len(old_cal) else ["playoff", po.PLAYOFF_WEEKS - 1]
        rounds_played = sum(1 for ev in old_cal[: self.week] if ev[0] == "league")
        if not legacy_sc and old_ev in self.calendar:
            self.week = self.calendar.index(old_ev)
        elif old_ev[0] == "playoff" or (old_ev[0] == "league" and len(old_ev) > 2):
            pw = old_ev[1] if old_ev[0] == "playoff" else old_ev[2]
            self.week = next(i for i in range(len(self.calendar)) if self._event(i)[2] == pw)
        else:
            self.week = next(
                i for i, ev in enumerate(self.calendar) if ev[0] == "league" and ev[1] == rounds_played
            )
        catch_up = WeekReport("catch-up")
        notes = []
        if legacy_sc:
            self.cup = cupmod.new_cup()
            self._cup_draw()
            for idx, rnd in enumerate(data.CUP_ROUNDS):
                if rnd[1] <= rounds_played:
                    self._play_cup_round(idx, catch_up, [], set())
            notes.append(f"The {data.CUP_NAME} now follows the official 2026-27 format.")
        self._new_league_cup()
        for md in range(lcup.MATCHDAYS):  # the group stage is pre-season, so always in the past
            self._play_league_cup_matchday(md, catch_up, [], set())
        for idx, (_, week) in enumerate(lcup.KO_ROUNDS):
            if week <= rounds_played:
                self._play_league_cup_round(idx, catch_up, [], set())
        notes.append(f"The {lcup.NAME} has been added - results so far are in the news.")
        mine = [
            f"{label}: {r.home} {r.home_goals}-{r.away_goals} {r.away}"
            + (f" ({r.pens} pens)" if r.pens else "")
            for label, results in catch_up.cup_rounds
            if label.startswith(lcup.NAME)
            for r in results
            if self.club_name in (r.home, r.away)
        ]
        self.news = (notes + catch_up.news + mine + self.news)[:40]

    def _play(self, home: str, away: str, cup: bool) -> MatchResult:
        hc, ac = self.clubs[home], self.clubs[away]
        return simulate_match(
            home,
            away,
            self.selected_players(home),
            self.selected_players(away),
            self.rng,
            hc.morale,
            ac.morale,
            cup=cup,
        )

    def _apply_league(self, res: MatchResult):
        th, ta = self.tables[res.home], self.tables[res.away]
        for row, gf, ga in ((th, res.home_goals, res.away_goals), (ta, res.away_goals, res.home_goals)):
            row["P"] += 1
            row["F"] += gf
            row["A"] += ga
            if gf > ga:
                row["W"] += 1
                row["Pts"] += 3
                row["form"] = (row["form"] + "W")[-5:]
            elif gf == ga:
                row["D"] += 1
                row["Pts"] += 1
                row["form"] = (row["form"] + "D")[-5:]
            else:
                row["L"] += 1
                row["form"] = (row["form"] + "L")[-5:]

    def _record_player_result(self, res: MatchResult):
        d = res.to_dict()
        d["label"] = self.event_label()
        self.player_results.append(d)
        stats.note_result(self.records, d, self.club_name, self.season_label)

    def _update_morale(self, res: MatchResult):
        for name in (res.home, res.away):
            c = self.clubs.get(name)
            if c is None:  # a non-league cup side that has already gone home
                continue
            if res.winner == name:
                c.morale += 8
            elif res.winner is None:
                c.morale += 1
            elif res.pens:
                c.morale -= 2
            else:
                c.morale -= 7
            c.morale = max(10, min(95, c.morale + (1 if c.morale < 50 else -1)))

    def _fitness_and_injuries(self, played: set[int], all_results: list[MatchResult], report: WeekReport):
        for p in self.players.values():
            if p.id in played:
                p.apps += 1
                p.energy = max(45, p.energy - self.rng.randint(6, 14))
            else:
                p.energy = min(100, p.energy + 14)
        for res in all_results:
            self._update_morale(res)
            for e in res.events:
                if e.kind == "goal" and e.player_id in self.players:
                    self.players[e.player_id].goals += 1
            for pid, weeks in res.injuries:
                p = self.players.get(pid)
                if p is None:
                    continue
                p.injury = weeks + 1  # +1 because the countdown ticks at the start of next week
                if p.club == self.club_name:
                    report.news.append(f"{p.name} is injured - out for {weeks} week(s).")
        self._update_form(all_results)
        self._apply_discipline(all_results, report)

    def _update_form(self, all_results: list[MatchResult]):
        """Blend each player's match into their form; anyone who didn't play drifts back to 0."""
        rating: dict[int, float] = {}
        for res in all_results:
            for club, xi, conceded in (
                (res.home, res.home_xi, res.away_goals),
                (res.away, res.away_xi, res.home_goals),
            ):
                result = FORM_PENS_RESULT if res.pens else FORM_RESULT
                if res.winner is None:
                    result = 0
                elif res.winner != club:
                    result = -result
                for pid in xi:
                    p = self.players.get(pid)
                    if p is None:  # a non-league cup side's player
                        continue
                    r = result
                    if p.pos in ("GK", "DEF"):
                        if conceded == 0:
                            r += FORM_CLEAN_SHEET
                        elif conceded >= 3:
                            r -= FORM_CLEAN_SHEET
                    rating[pid] = rating.get(pid, 0) + r
            for e in res.events:
                if e.player_id in rating:
                    if e.kind == "goal":
                        rating[e.player_id] += FORM_GOAL
                    elif e.kind == "red":
                        rating[e.player_id] += FORM_RED_CARD
        for p in self.players.values():
            if p.id in rating:
                match = (rating[p.id] + self.rng.gauss(0, FORM_NOISE)) * FORM_SCALE
                match = max(-FORM_MAX, min(FORM_MAX, match))
                p.form = round(FORM_KEEP * p.form + (1 - FORM_KEEP) * match)
            elif p.form:
                p.form -= 1 if p.form > 0 else -1

    def _drop_from_selection(self, p: Player):
        club = self.clubs.get(p.club)
        if club and p.id in club.selected:
            club.selected.remove(p.id)

    def _apply_discipline(self, results: list[MatchResult], report: WeekReport):
        """Serve bans for clubs that played, then hand out new ones.

        A second yellow is a one-match ban, a straight red two matches, and every fifth
        booking of the season a one-match ban.
        """
        clubs_played = {n for r in results for n in (r.home, r.away)}
        for p in self.players.values():
            if p.suspended and p.club in clubs_played:
                p.suspended -= 1  # sat this one out
        for res in results:
            for e in res.events:
                p = self.players.get(e.player_id)
                if p is None or e.kind not in ("yellow", "red"):
                    continue
                mine = p.club == self.club_name
                if e.kind == "red":
                    ban = 2 if e.detail == "straight" else 1
                    p.suspended += ban
                    self._drop_from_selection(p)
                    if mine:
                        how = "a straight red card" if e.detail == "straight" else "a second yellow card"
                        report.news.append(f"{p.name} was sent off ({how}) - banned for {ban} match(es).")
                else:
                    p.yellows += 1
                    if p.yellows % 5 == 0:
                        p.suspended += 1
                        self._drop_from_selection(p)
                        if mine:
                            report.news.append(f"{p.name} has {p.yellows} bookings - suspended for 1 match.")

    # finances ------------------------------------------------------------
    def _weekly_finances(self, home_game: bool, res: MatchResult | None) -> dict:
        club = self.club
        div = club.division
        f = {}
        if home_game and res is not None:
            fill = 0.35 + 0.004 * club.morale + (0.15 if div == 0 else 0)
            if res.away in self.divisions[0][:2] or res.home in self.divisions[0][:2]:
                fill += 0.2
            crowd = int(min(club.capacity, club.capacity * fill))
            f["Gate receipts"] = crowd * data.TICKET_PRICE[div]
            f["_crowd"] = crowd
        f["TV & sponsors"] = data.WEEKLY_INCOME[div]
        f["Wages"] = -self.wage_bill()
        f["Ground upkeep"] = -int(club.capacity * 0.45 + 1000)
        if self.loan:
            f["Loan interest"] = -int(self.loan * data.LOAN_WEEKLY_INTEREST)
        total = sum(v for k, v in f.items() if not k.startswith("_"))
        self.balance += total
        f["Net"] = total
        self.last_finance = f
        return f

    def _board_check(self, report: WeekReport):
        limit = data.OVERDRAFT_LIMIT[self.club.division]
        if self.balance < -limit:
            self.board_warnings += 1
            if self.board_warnings >= 4:
                self.sacked = True
                self.game_over_reason = "The board have lost patience with the club's debts."
                report.news.append("The board have lost patience with the club's debts. You are SACKED!")
            else:
                report.news.append(
                    f"BOARD WARNING {self.board_warnings}/3: the overdraft is over £{limit:,}. Sort it out!"
                )
        else:
            self.board_warnings = 0

    def borrow(self, amount: int) -> str:
        limit = data.LOAN_LIMIT[self.club.division]
        amount = min(amount, limit - self.loan)
        if amount <= 0:
            return f"The bank won't lend more than £{limit:,}."
        self.loan += amount
        self.balance += amount
        return f"Borrowed £{amount:,}."

    def repay(self, amount: int) -> str:
        amount = min(amount, self.loan, max(0, self.balance))
        if amount <= 0:
            return "Nothing to repay (or no cash to repay with)."
        self.loan -= amount
        self.balance -= amount
        return f"Repaid £{amount:,}."

    # transfers -----------------------------------------------------------
    def _refresh_market(self):
        div = self.club.division
        divs = {max(0, div - 1), div, min(3, div + 1)}
        pool = [
            p
            for p in self.players.values()
            if p.club != self.club_name and p.available and self.clubs[p.club].division in divs
        ]
        picks = self.rng.sample(pool, min(6, len(pool)))
        self.market = [[p.id, round_money(p.value * self.rng.uniform(1.0, 1.3))] for p in picks]

    def bid(self, player_id: int, amount: int) -> tuple[bool, str]:
        entry = next((m for m in self.market if m[0] == player_id), None)
        if entry is None:
            return False, "That player is no longer available."
        p = self.players[player_id]
        if len(self.squad(self.club_name)) >= MAX_SQUAD:
            return False, f"Your squad is full ({MAX_SQUAD} players)."
        if amount > self.balance:
            return False, "You can't afford that bid."
        asking = entry[1]
        if amount < asking * self.rng.uniform(0.8, 1.02):
            return False, f"{p.club} reject your bid of £{amount:,} for {p.name}."
        seller = p.club
        self.balance -= amount
        p.club = self.club_name
        p.energy = max(p.energy, 80)
        self.market.remove(entry)
        self._top_up_squad(seller)
        self.clubs[seller].selected = self.auto_pick(seller)
        return True, f"{p.name} signs from {seller} for £{amount:,}!"

    def sale_offer(self, player_id: int) -> tuple[str, int] | None:
        p = self.players[player_id]
        if len(self.squad(self.club_name)) <= MIN_SQUAD:
            return None
        target_div = max(0, min(3, self.club.division + self.rng.choice([-1, 0, 0, 1])))
        buyers = [n for n in self.divisions[target_div] if n != self.club_name]
        buyer = self.rng.choice(buyers)
        return buyer, round_money(p.value * self.rng.uniform(0.7, 1.15))

    def accept_sale(self, player_id: int, buyer: str, fee: int) -> str:
        p = self.players[player_id]
        p.club = buyer
        self.balance += fee
        if player_id in self.club.selected:
            self.club.selected.remove(player_id)
        return f"{p.name} sold to {buyer} for £{fee:,}."

    # editor support ------------------------------------------------------
    def add_player(self, club: str, name: str, pos: str, skill: int, age: int) -> Player:
        p = Player(id=self.next_id, name=name, pos=pos, skill=skill, age=age, club=club)
        self.next_id += 1
        self.players[p.id] = p
        return p

    def _detach(self, player_id: int):
        """Take a player out of his club's line-up and off the transfer list."""
        p = self.players[player_id]
        club = self.clubs.get(p.club)
        if club and player_id in club.selected:
            club.selected.remove(player_id)
        self.market = [m for m in self.market if m[0] != player_id]

    def remove_player(self, player_id: int) -> str:
        p = self.players[player_id]
        if len(self.squad(p.club)) <= MIN_SQUAD:
            return f"{p.club} need at least {MIN_SQUAD} players."
        self._detach(player_id)
        del self.players[player_id]
        return ""

    def move_player(self, player_id: int, dest: str) -> str:
        p = self.players[player_id]
        if len(self.squad(p.club)) <= MIN_SQUAD:
            return f"{p.club} need at least {MIN_SQUAD} players."
        self._detach(player_id)
        p.club = dest
        return ""

    def copy(self) -> Game:
        return Game.from_dict(self.to_dict())

    def _top_up_squad(self, club: str, target: int = 0):
        """Bring youngsters in: first to cover every position, then up to `target` players."""
        squad = self.squad(club)
        counts = {pos: sum(1 for p in squad if p.pos == pos) for pos in FORMATION_442}
        need = {"GK": 2, "DEF": 4, "MID": 4, "ATT": 2}
        rating = self.clubs[club].rating - 4
        for pos, n in need.items():
            for _ in range(n - counts[pos]):
                self._new_player(club, pos, rating, age=self.rng.randint(17, 20))
                counts[pos] += 1
        ideal = {"GK": 2, "DEF": 6, "MID": 6, "ATT": 4}
        while sum(counts.values()) < target:
            pos = min(ideal, key=lambda k: counts[k] / ideal[k])
            self._new_player(club, pos, rating, age=self.rng.randint(17, 19))
            counts[pos] += 1

    def _drop_to_non_league(self, name: str):
        """A club relegated out of the SPFL joins the pyramid and can come back later."""
        c = self.clubs[name]
        if not any(n["name"] == name for n in self.non_league):
            self.non_league.append(
                {
                    "league": self.rng.choice(["HL", "LL"]),
                    "name": c.name,
                    "short": c.short,
                    "shirt": list(c.shirt),
                    "shorts": list(c.shorts),
                    "stadium": c.stadium,
                    "capacity": c.capacity,
                    "rating": max(25, c.rating - 3),
                    "pattern": c.pattern,
                    "shirt2": list(c.shirt2),
                }
            )
        self._remove_club(name)

    def _remove_club(self, name: str):
        """A club leaves the SPFL (or a beaten pyramid challenger goes home)."""
        for pid in [p.id for p in self.players.values() if p.club == name]:
            del self.players[pid]
        self.clubs.pop(name, None)
        self.tables.pop(name, None)
        for div in self.divisions:
            if name in div:
                div.remove(name)
        self.market = [m for m in self.market if m[0] in self.players]

    def _move_division(self, name: str, new_div: int):
        for div in self.divisions:
            if name in div:
                div.remove(name)
        self.divisions[new_div].append(name)
        self.clubs[name].division = new_div

    # season end ----------------------------------------------------------
    def _end_season(self) -> dict:
        summary = {"season": self.season_label, "champions": [], "promoted": [], "relegated": []}
        finals = [[n for n, _ in self.table(d)] for d in range(4)]
        for order in finals:
            summary["champions"].append(order[0])
        my_div = self.club.division
        my_pos = finals[my_div].index(self.club_name) + 1
        prize = int(data.SEASON_PRIZE_TOP[my_div] * (1 - (my_pos - 1) / len(finals[my_div])))
        self.balance += prize
        summary["position"] = my_pos
        summary["division"] = data.DIVISION_FULL[my_div]
        summary["prize"] = prize
        summary["cup_winner"] = self.cup.get("winner", "")
        summary["league_cup_winner"] = self.league_cup.get("winner", "")
        # next season: League Cup seeding comes from these final positions, and the top four in
        # the Premiership plus the Scottish Cup winners (or 5th place) go into Europe
        self.prev_order = [c for div in finals for c in div]
        top4 = finals[0][:4]
        sc_winner = self.cup.get("winner", "")
        fifth = sc_winner if sc_winner in finals[0] and sc_winner not in top4 else finals[0][4]
        self.europe = top4 + [fifth]

        # automatic promotion and relegation: champions up, bottom club down
        moves = []
        for d in range(3):
            moves += [(finals[d + 1][0], d), (finals[d][-1], d + 1)]
        # play-off finals: the winner plays in the higher division
        summary["playoffs"] = []
        for key, d in (("prem_f", 0), ("champ_f", 1), ("l1_f", 2)):
            tie = po.get(self.playoffs, key)
            if tie and tie["winner"]:
                summary["playoffs"].append(
                    f"{po.tie_name(tie)}: {tie['winner']} beat {tie['loser']} ({tie['note']})"
                )
                if tie["winner"] != tie["stay"]:
                    moves += [(tie["winner"], d), (tie["stay"], d + 1)]
        for name, d in moves:
            old_div = self.clubs[name].division
            (summary["promoted"] if d < old_div else summary["relegated"]).append(name)
            self._move_division(name, d)

        tie = po.get(self.playoffs, "l2_f")
        if tie and tie["winner"]:
            summary["playoffs"].append(
                f"{po.tie_name(tie)}: {tie['winner']} beat {tie['loser']} ({tie['note']})"
            )
            challenger = self.playoffs["entrant"]
            if tie["winner"] == challenger:
                dropped = tie["stay"]
                summary["relegated"].append(f"{dropped} (out of the SPFL)")
                summary["promoted"].append(f"{challenger} (into the SPFL)")
                if dropped == self.club_name:
                    self.sacked = True
                    summary["dropped_out"] = True
                    self.game_over_reason = f"{dropped} have dropped out of the SPFL."
                else:
                    self._drop_to_non_league(dropped)
                self.non_league = [n for n in self.non_league if n["name"] != challenger]
                self._move_division(challenger, 3)
                self.tables[challenger] = empty_row()
            else:
                self._remove_club(challenger)
        elif self.playoffs.get("entrant") in self.clubs:
            self._remove_club(self.playoffs["entrant"])

        # non-league cup sides and a beaten pyramid challenger go back to their own leagues
        for name in [n for n, c in self.clubs.items() if c.division == 4]:
            self._remove_club(name)

        # top scorers by the division each club finished in (before promotion and relegation)
        finished_in = {club: d for d, order in enumerate(finals) for club in order}
        top_scorers = []
        for d in range(4):
            best = max(
                (p for p in self.players.values() if finished_in.get(p.club) == d),
                key=lambda p: p.goals,
                default=None,
            )
            top_scorers.append([best.name, best.club, best.goals] if best and best.goals else None)
        if top_scorers[my_div]:
            name, club, goals = top_scorers[my_div]
            summary["top_scorer"] = f"{name} ({club}) {goals} goals"
        mine = max(self.squad(self.club_name), key=lambda p: p.goals, default=None)
        if mine and mine.goals > self.records.get("top_scorer", {}).get("goals", 0):
            self.records["top_scorer"] = {
                "name": mine.name,
                "goals": mine.goals,
                "season": self.season_label,
                "club": self.club_name,
            }

        self.history.append(
            {
                "season": self.season_label,
                "club": self.club_name,
                "division": summary["division"],
                "position": my_pos,
                "points": self.tables[self.club_name]["Pts"],
                "champions": summary["champions"],
                "cup_winner": summary["cup_winner"],
                "league_cup_winner": summary["league_cup_winner"],
                "top_scorers": top_scorers,
            }
        )

        # ageing, development and retirements
        for p in list(self.players.values()):
            p.age += 1
            if p.age <= 23:
                p.skill += self.rng.randint(0, 5)
            elif p.age >= 31:
                p.skill -= self.rng.randint(0, 5)
            else:
                p.skill += self.rng.randint(-2, 2)
            p.skill = max(8, min(99, p.skill))
            p.energy = 100
            p.injury = 0
            p.yellows = 0  # bookings are wiped at the end of the season (bans carry over)
            if p.age >= 36 or (p.age >= 34 and self.rng.random() < 0.4):
                del self.players[p.id]
        for c in self.clubs.values():
            self._top_up_squad(c.name, target=YOUTH_TARGET)
            c.morale = 50
            c.selected = self.auto_pick(c.name)

        if self.sacked:
            summary["sacked"] = True
            return summary
        if self.balance < -data.OVERDRAFT_LIMIT[self.club.division]:
            self.sacked = True
            summary["sacked"] = True
            self.game_over_reason = "The board have lost patience with the club's debts."

        self.season += 1
        self._start_season()
        summary["new_division"] = data.DIVISION_FULL[self.club.division]
        return summary

    # ------------------------------------------------------------ save/load
    def to_dict(self) -> dict:
        state = self.rng.getstate()
        return {
            "version": SAVE_VERSION,
            "rng": [state[0], list(state[1]), state[2]],
            "manager": self.manager,
            "club_name": self.club_name,
            "season": self.season,
            "week": self.week,
            "clubs": [c.to_dict() for c in self.clubs.values()],
            "players": [p.to_dict() for p in self.players.values()],
            "divisions": self.divisions,
            "fixtures": self.fixtures,
            "tables": self.tables,
            "cup": self.cup,
            "balance": self.balance,
            "loan": self.loan,
            "market": self.market,
            "news": self.news,
            "history": self.history,
            "records": self.records,
            "player_results": self.player_results,
            "next_id": self.next_id,
            "board_warnings": self.board_warnings,
            "sacked": self.sacked,
            "last_finance": self.last_finance,
            "playoffs": self.playoffs,
            "split": self.split,
            "calendar": self.calendar,
            "league_cup": self.league_cup,
            "europe": self.europe,
            "prev_order": self.prev_order,
            "pyramid_champions": self.pyramid_champions,
            "non_league": self.non_league,
            "game_over_reason": self.game_over_reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Game:
        if d.get("version", 1) < SAVE_VERSION:
            raise ValueError(
                "this save is from an older version with made-up squads - please start a new game"
            )
        g = cls()
        v, internal, gauss = d["rng"]
        g.rng.setstate((v, tuple(internal), gauss))
        g.manager = d["manager"]
        g.club_name = d["club_name"]
        g.season = d["season"]
        g.week = d["week"]
        g.clubs = {c["name"]: Club.from_dict(c) for c in d["clubs"]}
        g.players = {p["id"]: Player.from_dict(p) for p in d["players"]}
        g.divisions = d["divisions"]
        g.fixtures = d["fixtures"]
        g.tables = d["tables"]
        g.cup = d["cup"]
        g.balance = d["balance"]
        g.loan = d["loan"]
        g.market = d["market"]
        g.news = d["news"]
        g.history = d["history"]
        g.records = d.get("records", {})
        g.player_results = d["player_results"]
        g.next_id = d["next_id"]
        g.board_warnings = d["board_warnings"]
        g.sacked = d["sacked"]
        g.last_finance = d.get("last_finance", {})
        g.playoffs = d.get("playoffs", {})
        legacy_cup = "remaining" not in g.cup
        g.split = d.get("split", {})
        g.league_cup = d.get("league_cup", {})
        g.europe = d.get("europe", list(lcup.REAL_2026_EUROPE))
        g.prev_order = d.get("prev_order", [])
        g.pyramid_champions = d.get("pyramid_champions", [])
        g.non_league = d.get("non_league", g.non_league)
        g.game_over_reason = d.get("game_over_reason", "")
        if "calendar" in d:
            g.calendar = d["calendar"]
        else:  # a save from before v0.11: move it onto the current calendar
            g._migrate_old_save(legacy_sc=legacy_cup)
        return g

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict()))

    @classmethod
    def load(cls, path: Path) -> Game:
        return cls.from_dict(json.loads(path.read_text()))


def save_path() -> Path:
    return Path.home() / ".spfl_manager" / "savegame.json"
