"""Season stats and all-time records, worked out from the game state for the Stats & Records screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import data

if TYPE_CHECKING:
    from .game import Game
    from .models import Player

IN_FORM_MIN_APPS = 3  # one good game isn't a run of form


def top_scorers(g: Game, div: int, n: int = 14) -> list[Player]:
    """The Golden Boot race in one division: goals in every competition this season."""
    clubs = set(g.divisions[div])
    scorers = [p for p in g.players.values() if p.club in clubs and p.goals > 0]
    return sorted(scorers, key=lambda p: (-p.goals, p.apps, p.name))[:n]


def in_form(g: Game, n: int = 14) -> list[Player]:
    """The SPFL's hottest players (regular starters only)."""
    spfl = {c for div in g.divisions for c in div}
    regulars = [p for p in g.players.values() if p.club in spfl and p.apps >= IN_FORM_MIN_APPS and p.form > 0]
    return sorted(regulars, key=lambda p: (-p.form, -p.goals, p.name))[:n]


def club_stats(g: Game, club: str) -> list[Player]:
    """A club's players, leading scorers first, then the most appearances."""
    return sorted(g.squad(club), key=lambda p: (-p.goals, -p.apps, p.name))


def _for_against(res: dict, club: str) -> tuple[int, int]:
    if res["home"] == club:
        return res["home_goals"], res["away_goals"]
    return res["away_goals"], res["home_goals"]


def season_record(g: Game) -> dict:
    """The manager's club this season in every competition: P W D L F A (shoot-outs count as draws)."""
    rec = {"P": 0, "W": 0, "D": 0, "L": 0, "F": 0, "A": 0}
    for res in g.player_results:
        f, a = _for_against(res, g.club_name)
        rec["P"] += 1
        rec["F"] += f
        rec["A"] += a
        rec["W" if f > a else "L" if f < a else "D"] += 1
    return rec


def note_result(records: dict, res: dict, club: str, season: str) -> None:
    """Keep the manager's biggest win and heaviest defeat. res is a MatchResult dict with a label."""
    f, a = _for_against(res, club)
    if f == a:
        return
    key = "biggest_win" if f > a else "heaviest_defeat"
    margin, goals = abs(f - a), max(f, a)
    best = records.get(key)
    if best and (margin, goals) <= (best["margin"], best["goals"]):
        return  # the earlier one stays the record
    records[key] = {
        "margin": margin,
        "goals": goals,
        "score": f"{f}-{a}",
        "opponent": res["away"] if res["home"] == club else res["home"],
        "venue": "home" if res["home"] == club else "away",
        "competition": res.get("label", ""),
        "season": season,
        "club": club,
    }


def trophies(history: list[dict]) -> list[str]:
    """Everything the manager has won, oldest first, from the season history."""
    won = []
    for h in history:
        club, season = h["club"], h["season"]
        champions = h.get("champions", [])
        div = data.DIVISION_FULL.index(h["division"]) if h["division"] in data.DIVISION_FULL else -1
        if 0 <= div < len(champions) and champions[div] == club:
            won.append(f"{season}  {data.DIVISIONS[div]} champions")
        if h.get("cup_winner") == club:
            won.append(f"{season}  Scottish Cup")
        if h.get("league_cup_winner") == club:
            won.append(f"{season}  League Cup")
    return won


def best_finish(history: list[dict]) -> dict | None:
    """The manager's highest league finish: the top division first, then the position."""

    def rank(h):
        div = data.DIVISION_FULL.index(h["division"]) if h["division"] in data.DIVISION_FULL else 9
        return div, h["position"]

    return min(history, key=rank, default=None)
