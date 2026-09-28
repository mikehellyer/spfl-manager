"""Core data models: players, clubs and team strength."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

POSITIONS = ("GK", "DEF", "MID", "ATT")


def round_money(amount: float) -> int:
    if amount >= 100_000:
        step = 5_000
    elif amount >= 10_000:
        step = 1_000
    else:
        step = 250
    return max(step, int(round(amount / step) * step))


@dataclass
class Player:
    id: int
    name: str
    pos: str
    skill: int
    age: int
    club: str
    energy: int = 100
    injury: int = 0  # weeks remaining out
    goals: int = 0
    apps: int = 0

    @property
    def short_name(self) -> str:
        """Full name if it fits a table column, otherwise 'J. Surname'."""
        if len(self.name) <= 15 or " " not in self.name:
            return self.name
        first, rest = self.name.split(" ", 1)
        return f"{first[0]}. {rest}"[:15]

    @property
    def available(self) -> bool:
        return self.injury == 0

    @property
    def effective(self) -> float:
        """Skill adjusted for fitness - a tired player plays worse."""
        return self.skill * (0.65 + 0.35 * self.energy / 100)

    @property
    def value(self) -> int:
        base = (self.skill / 10) ** 3 * 1_100
        if self.age <= 21:
            base *= 1.35
        elif self.age <= 25:
            base *= 1.15
        elif self.age >= 33:
            base *= 0.45
        elif self.age >= 30:
            base *= 0.7
        return round_money(base)

    @property
    def wage(self) -> int:
        """Weekly wage."""
        return int(round((self.skill / 10) ** 2.6 * 20 / 10) * 10)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Player":
        return cls(**d)


@dataclass
class Club:
    name: str
    short: str
    division: int
    shirt: tuple
    shorts: tuple
    stadium: str
    capacity: int
    rating: int
    morale: int = 50
    selected: list = field(default_factory=list)  # player ids in the starting XI
    pattern: str = ""  # "", "stripes" or "hoops"
    shirt2: tuple = (240, 240, 240)

    @property
    def kit(self) -> tuple:
        return self.shirt, self.shorts, self.pattern, self.shirt2

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("shirt", "shorts", "shirt2"):
            d[k] = list(getattr(self, k))
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Club":
        d = dict(d)
        for k in ("shirt", "shorts", "shirt2"):
            if k in d:
                d[k] = tuple(d[k])
        return cls(**d)


@dataclass
class Strength:
    defence: float
    midfield: float
    attack: float

    @property
    def overall(self) -> float:
        return (self.defence + self.midfield + self.attack) / 3


def _compress(ratio: float) -> float:
    """Diminishing returns for stacking one area of the pitch."""
    return ratio if ratio <= 1 else 1 + (ratio - 1) * 0.4


def team_strength(players: list[Player]) -> Strength:
    """Work out defence / midfield / attack ratings for a starting line-up.

    The formula is balanced so that a 4-4-2 of equal players rates every
    area at roughly that players' skill. Extra defenders boost defence at the
    cost of midfield and attack, and so on - just like the old game.
    """
    if not players:
        return Strength(1, 1, 1)
    eff = {p.id: p.effective for p in players}
    keepers = sorted((p for p in players if p.pos == "GK"), key=lambda p: -eff[p.id])
    outfield = [p for p in players if p.pos != "GK"]
    if keepers:
        keeper = eff[keepers[0].id]
        # spare keepers play outfield, badly
        dfs = sum(eff[p.id] for p in players if p.pos == "DEF") + 0.5 * sum(
            eff[p.id] for p in keepers[1:]
        )
    else:
        keeper = 0.35 * max((eff[p.id] for p in outfield), default=1)
        dfs = sum(eff[p.id] for p in players if p.pos == "DEF")
    mds = sum(eff[p.id] for p in players if p.pos == "MID")
    ats = sum(eff[p.id] for p in players if p.pos == "ATT")

    mean = max(1.0, sum(eff.values()) / 11)
    defence = (1.2 * keeper + dfs + 0.3 * mds) / 6.4
    midfield = (mds + 0.25 * (dfs + ats)) / 5.5
    attack = (ats + 0.3 * mds) / 3.2
    return Strength(
        defence=mean * _compress(defence / mean),
        midfield=mean * _compress(midfield / mean),
        attack=mean * _compress(attack / mean),
    )
