"""The Scottish Cup: who enters when, draws, and non-league clubs.

Follows the Scottish FA's 2026-27 format (see data.CUP_ROUNDS): three
preliminary rounds and Round One for non-league clubs only, League Two
enters in Round Two, League One and the Championship in Round Three, and
the Premiership in Round Four.

Cup state (saved in the game) is a plain dict:
    round      index of the next round to play
    remaining  clubs through to the next round (not yet drawn)
    ties       the draw for the next round: [[home, away], ...]
    byes       clubs given a bye in the next round
    ratings    strength of every non-league club still involved
    winner     the winner, once the final is played
    out        True once the manager's club has been knocked out
"""

from __future__ import annotations

import random
import zlib

from . import data
from .fixtures import cup_draw
from .match import MatchResult, poisson

KIT_CHOICES = [
    ((200, 30, 30), (240, 240, 240), "", (240, 240, 240)),
    ((20, 60, 170), (240, 240, 240), "", (240, 240, 240)),
    ((0, 120, 60), (240, 240, 240), "", (240, 240, 240)),
    ((240, 240, 240), (20, 20, 20), "", (240, 240, 240)),
    ((20, 20, 20), (20, 20, 20), "stripes", (240, 240, 240)),
    ((250, 200, 20), (20, 20, 20), "", (250, 200, 20)),
    ((120, 20, 40), (240, 240, 240), "", (120, 20, 40)),
    ((110, 180, 230), (20, 40, 90), "", (110, 180, 230)),
    ((200, 30, 30), (20, 20, 20), "hoops", (240, 240, 240)),
    ((20, 60, 170), (20, 60, 170), "hoops", (240, 240, 240)),
]


# shorter forms for names that don't fit a results column
SHORT_NAMES = {
    "University of Stirling": "Univ. of Stirling",
    "Hill of Beath Hawthorn": "Hill of Beath Haw.",
    "Gala Fairydean Rovers": "Gala Fairydean Rov.",
    "Civil Service Strollers": "Civil Service Str.",
    "Kirkintilloch Rob Roy": "Kirkintilloch R.R.",
    "St Cuthbert Wanderers": "St Cuthbert Wand.",
    "Inverurie Loco Works": "Inverurie Locos",
    "Heart of Midlothian": "Hearts",
}


def display_name(name: str, width: int = 19) -> str:
    name = SHORT_NAMES.get(name, name)
    return name if len(name) <= width else name[: width - 1] + "."


def round_name(idx: int) -> str:
    return data.CUP_ROUNDS[idx][0]


def label(idx: int) -> str:
    return f"{data.CUP_NAME} {round_name(idx)}"


def attached_rounds(league_week: int) -> list[int]:
    """Non-league-only rounds played on the same weekend as this league week (1-based)."""
    return [i for i, r in enumerate(data.CUP_ROUNDS) if r[1] == league_week and i < data.FIRST_SPFL_ROUND]


def event_rounds(league_week: int) -> list[int]:
    """Cup weekends (SPFL clubs involved) that come after this league week (1-based)."""
    return [i for i, r in enumerate(data.CUP_ROUNDS) if r[1] == league_week and i >= data.FIRST_SPFL_ROUND]


def entry_round(division: int) -> int:
    """Which round an SPFL division enters."""
    group = {0: "premiership", 1: "league_one_championship", 2: "league_one_championship", 3: "league_two"}[
        division
    ]
    return next(i for i, r in enumerate(data.CUP_ROUNDS) if r[2] == group)


def non_league_rating(name: str, group: str) -> int:
    return data.NON_LEAGUE_RATINGS.get(name, data.NON_LEAGUE_RATING[group])


def kit_for(name: str) -> tuple:
    """A made-up but stable kit for a non-league club."""
    return KIT_CHOICES[zlib.crc32(name.encode()) % len(KIT_CHOICES)]


def short_code(name: str) -> str:
    word = name.replace("The ", "").replace("St ", "St")
    letters = "".join(ch for ch in word if ch.isalpha())
    return letters[:3].upper()


def new_cup() -> dict:
    return {"round": 0, "remaining": [], "ties": [], "byes": [], "ratings": {}, "winner": "", "out": False}


def entrants(game, cup: dict, idx: int) -> list[str]:
    """Clubs who join the competition in round `idx`."""
    group = data.CUP_ROUNDS[idx][2]
    spfl = {c for div in game.divisions for c in div}
    if group == "prelim":
        names = [n for n in data.CUP_PRELIM_CLUBS if n not in spfl]
        for n in names:
            cup["ratings"][n] = non_league_rating(n, "prelim")
        return names
    if group == "senior_non_league":
        names = []
        for n in data.CUP_HIGHLAND_CLUBS:
            if n not in spfl:
                cup["ratings"][n] = non_league_rating(n, "highland")
                names.append(n)
        for n in data.CUP_LOWLAND_CLUBS:
            if n not in spfl:
                cup["ratings"][n] = non_league_rating(n, "lowland")
                names.append(n)
        # clubs that have dropped out of the SPFL play in the Highland/Lowland leagues now
        for club in game.non_league:
            if club["name"] not in spfl and club["name"] not in names:
                cup["ratings"][club["name"]] = club["rating"]
                names.append(club["name"])
        return names
    if group == "league_two":
        return list(game.divisions[3])
    if group == "league_one_championship":
        return list(game.divisions[1]) + list(game.divisions[2])
    if group == "premiership":
        return list(game.divisions[0])
    return []


def make_draw(game, cup: dict, rng: random.Random):
    """Draw the next round: everyone still in plus this round's entrants."""
    idx = cup["round"]
    teams = cup["remaining"] + entrants(game, cup, idx)
    cup["remaining"] = []
    rng.shuffle(teams)
    byes = data.CUP_ROUNDS[idx][3]
    if (len(teams) - byes) % 2:
        byes += 1  # an odd number of teams: one extra club gets a bye
    cup["byes"] = teams[:byes]
    cup["ties"] = cup_draw(teams[byes:], rng)


def quick_result(home: str, away: str, rh: float, ra: float, rng: random.Random) -> MatchResult:
    """Score for a tie between two clubs without squads (non-league v non-league)."""
    h = rh * 1.06  # home advantage
    exp_h = 1.3 * (h / ra) ** 1.6
    exp_a = 1.3 * (ra / h) ** 1.6
    res = MatchResult(home, away, poisson(exp_h, rng), poisson(exp_a, rng))
    if res.home_goals == res.away_goals:
        home_wins = rng.random() < h / (h + ra)
        win = rng.randint(3, 5)
        lose = rng.randint(max(0, win - 3), win - 1)
        res.pens = f"{win}-{lose}" if home_wins else f"{lose}-{win}"
    return res
