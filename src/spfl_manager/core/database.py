"""The squad database: real squads shipped with the game plus the player's own edits.

The shipped file (squads.json next to this module) is never modified. The
squad editor saves a full copy to the user's data folder, and that copy is
used for new games whenever it exists.

Each player record is a dict:
    name, pos (GK/DEF/MID/ATT), no (shirt number as text), nat,
    notable (has a Wikipedia article), loan, born ("YYYY-MM-DD"),
    skill / age  - only present when set by hand in the editor.
"""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path

from . import data

DEFAULT_FILE = Path(__file__).with_name("squads.json")
POSITIONS = ("GK", "DEF", "MID", "ATT")
START_YEAR = 2026


def user_file() -> Path:
    return Path.home() / ".spfl_manager" / "squads.json"


def default_ratings() -> dict[str, int]:
    return {c.name: c.rating for div in data.CLUBS for c in div}


class SquadDB:
    def __init__(self, clubs: dict, ratings: dict | None = None, custom: bool = False):
        self.clubs: dict[str, list[dict]] = clubs
        self.ratings: dict[str, int] = default_ratings()
        self.ratings.update(ratings or {})
        self.custom = custom  # True when loaded from the user's edited copy

    # ------------------------------------------------------------ load/save
    @classmethod
    def load_default(cls) -> SquadDB:
        try:
            raw = json.loads(DEFAULT_FILE.read_text(encoding="utf-8"))
            return cls(raw.get("clubs", {}))
        except (OSError, ValueError):
            return cls({})

    @classmethod
    def load(cls, path: Path | None = None) -> SquadDB:
        path = path or user_file()
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                return cls(raw["clubs"], raw.get("ratings"), custom=True)
            except (OSError, ValueError, KeyError):
                pass  # damaged edits file - fall back to the shipped data
        return cls.load_default()

    def save(self, path: Path | None = None):
        path = path or user_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        defaults = default_ratings()
        ratings = {k: v for k, v in self.ratings.items() if defaults.get(k) != v}
        payload = {"_about": "SPFL Manager squad database (edited)", "clubs": self.clubs, "ratings": ratings}
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
        self.custom = True

    @staticmethod
    def reset(path: Path | None = None) -> SquadDB:
        path = path or user_file()
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return SquadDB.load_default()

    def copy(self) -> SquadDB:
        return SquadDB(copy.deepcopy(self.clubs), dict(self.ratings), self.custom)

    # ------------------------------------------------------------ queries
    def squad(self, club: str) -> list[dict]:
        return self.clubs.setdefault(club, [])

    def rating(self, club: str) -> int:
        return self.ratings.get(club, 40)

    def stats(self, club: str, rec: dict, season: int = START_YEAR) -> tuple[int, int, bool, bool]:
        """(skill, age, skill_is_estimate, age_is_estimate) for a player record.

        Estimates are seeded from the player's club and name, so they are the
        same every time - the editor shows exactly what a new game will use.
        """
        rng = random.Random(f"{club}|{rec.get('name', '')}")
        try:
            number = int(rec.get("no") or 0)
        except ValueError:
            number = 0
        young = number >= 30

        if "skill" in rec:
            skill, est_skill = int(rec["skill"]), False
        else:
            bonus = (3 if rec.get("notable") else 0) + (2 if 1 <= number <= 11 else 0) - (5 if young else 0)
            skill, est_skill = int(rng.gauss(self.rating(club) + bonus, 4)), True
        skill = max(1, min(99, skill))

        est_age = False
        born = rec.get("born", "")
        if "age" in rec:
            age = int(rec["age"]) + (season - START_YEAR)
        elif len(born) >= 4 and born[:4].isdigit():
            age = season - int(born[:4]) - (1 if born[5:10] > "07-01" else 0)
        else:
            age = rng.randint(17, 20) if young else rng.randint(19, 33)
            est_age = True
        return skill, max(15, min(45, age)), est_skill, est_age

    # ------------------------------------------------------------ edits
    def add_player(self, club: str, rec: dict):
        self.squad(club).append(rec)
        self.sort(club)

    def remove_player(self, club: str, rec: dict):
        self.squad(club).remove(rec)

    def move_player(self, rec: dict, from_club: str, to_club: str):
        self.remove_player(from_club, rec)
        rec.pop("loan", None)
        self.add_player(to_club, rec)

    def sort(self, club: str):
        def key(r):
            try:
                n = int(r.get("no") or 999)
            except ValueError:
                n = 999
            return (n, r.get("name", ""))

        self.squad(club).sort(key=key)
