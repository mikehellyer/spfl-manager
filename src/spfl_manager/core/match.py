"""Match engine: turns two line-ups into a result plus a list of highlight events."""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field

from .models import Player, team_strength

POS_SHOT_WEIGHT = {"ATT": 5.0, "MID": 2.5, "DEF": 1.0, "GK": 0.0}
# refereeing decisions that go against a side (flavour only - they never change the score)
DECISIONS = ["offside", "penalty", "free_kick"]
DECISION_WEIGHTS = [3, 2, 3]
# discipline: roughly the SPFL's rates (about 1.7 bookings per team per game, a red card
# in about one game in five). Defenders and midfielders pick up most of the cards.
YELLOWS_PER_TEAM = 1.7
STRAIGHT_REDS_PER_TEAM = 0.04
CARD_WEIGHT = {"DEF": 3.0, "MID": 2.5, "ATT": 1.5, "GK": 0.3}
SECOND_YELLOW_RISK = 0.35  # a booked player is careful: most of the time the card goes elsewhere
# playing with ten men: fewer chances made, more conceded (scaled by time left)
TEN_MEN_ATTACK = 0.3
TEN_MEN_DEFENCE = 0.25
DECISIONS_PER_TEAM = 0.8
HOME_BONUS = 1.06
FORM_ON_THE_DAY = 0.08  # spread of each side's day-to-day form (log scale)


@dataclass
class MatchEvent:
    minute: int
    side: str  # "home" or "away"
    kind: str  # goal | saved | miss | post | injury | decision | yellow | red
    player: str
    keeper: str = ""
    player_id: int = 0
    detail: str = ""  # decisions: offside | penalty | free_kick;  red cards: second_yellow | straight

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatchResult:
    home: str
    away: str
    home_goals: int = 0
    away_goals: int = 0
    events: list = field(default_factory=list)
    pens: str = ""  # "" or e.g. "4-3" (home-away) when a cup tie went to penalties
    home_xi: list = field(default_factory=list)
    away_xi: list = field(default_factory=list)
    injuries: list = field(default_factory=list)  # [player_id, weeks]

    @property
    def winner(self) -> str | None:
        if self.home_goals > self.away_goals:
            return self.home
        if self.away_goals > self.home_goals:
            return self.away
        if self.pens:
            h, a = (int(x) for x in self.pens.split("-"))
            return self.home if h > a else self.away
        return None

    def score_text(self) -> str:
        s = f"{self.home_goals}-{self.away_goals}"
        if self.pens:
            s += f" ({self.pens} pens)"
        return s

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> MatchResult:
        d = dict(d)
        d["events"] = [MatchEvent(**e) for e in d.get("events", [])]
        return cls(**d)


def poisson(lam: float, rng: random.Random) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _pick_shooter(xi: list[Player], rng: random.Random) -> Player:
    weights = [POS_SHOT_WEIGHT[p.pos] * p.effective + 0.01 for p in xi]
    return rng.choices(xi, weights=weights)[0]


def _keeper(xi: list[Player]) -> Player | None:
    gks = [p for p in xi if p.pos == "GK"]
    return max(gks, key=lambda p: p.effective) if gks else None


def simulate_match(
    home: str,
    away: str,
    home_xi: list[Player],
    away_xi: list[Player],
    rng: random.Random,
    home_morale: int = 50,
    away_morale: int = 50,
    cup: bool = False,
) -> MatchResult:
    hs, as_ = team_strength(home_xi), team_strength(away_xi)
    # form on the day: a little randomness so the underdog can sometimes spring a shock
    hm = (0.9 + 0.2 * home_morale / 100) * HOME_BONUS * math.exp(rng.gauss(0, FORM_ON_THE_DAY))
    am = (0.9 + 0.2 * away_morale / 100) * math.exp(rng.gauss(0, FORM_ON_THE_DAY))

    h_mid, a_mid = hs.midfield * hm, as_.midfield * am
    poss_home = h_mid**1.5 / (h_mid**1.5 + a_mid**1.5)

    def chances_and_conversion(att, opp_def, poss):
        # The quality gap raises both the number of chances and how many go in, but
        # gently: overall goals scale roughly in proportion to the gap (not its square),
        # so Premiership v League Two is typically 3-0 or 4-0 rather than 10-0.
        ratio = att / max(1.0, opp_def)
        expected = 9.0 * poss * ratio**0.4
        conv = min(0.5, max(0.08, 0.30 * ratio**0.6))
        return expected, conv

    result = MatchResult(home, away, home_xi=[p.id for p in home_xi], away_xi=[p.id for p in away_xi])
    events: list[MatchEvent] = []

    # discipline first, because a red card changes the rest of the game
    sent_off: dict[int, int] = {}  # player id -> minute sent off
    red_minute: dict[str, int | None] = {"home": None, "away": None}
    for side, xi in (("home", home_xi), ("away", away_xi)):
        outfield = [p for p in xi if p.pos != "GK"] or xi
        if not outfield:
            continue
        booked: set[int] = set()
        cards = [(rng.randint(1, 90), "yellow") for _ in range(poisson(YELLOWS_PER_TEAM, rng))]
        cards += [(rng.randint(1, 90), "straight") for _ in range(poisson(STRAIGHT_REDS_PER_TEAM, rng))]
        for minute, card in sorted(cards):
            still_on = [p for p in outfield if p.id not in sent_off]
            if not still_on:
                break
            p = rng.choices(still_on, weights=[CARD_WEIGHT[q.pos] for q in still_on])[0]
            if card == "yellow" and p.id in booked and rng.random() > SECOND_YELLOW_RISK:
                clean = [q for q in still_on if q.id not in booked]
                if clean:  # he stays out of trouble - someone else goes in the book
                    p = rng.choices(clean, weights=[CARD_WEIGHT[q.pos] for q in clean])[0]
            if card == "straight" or p.id in booked:
                detail = "straight" if card == "straight" else "second_yellow"
                events.append(MatchEvent(minute, side, "red", p.name, "", p.id, detail))
                sent_off[p.id] = minute
                if red_minute[side] is None:
                    red_minute[side] = minute
            else:
                booked.add(p.id)
                events.append(MatchEvent(minute, side, "yellow", p.name, "", p.id))

    def on_pitch(xi, minute):
        return [p for p in xi if sent_off.get(p.id, 999) > minute] or xi

    def man_down(side):  # share of the match played a man short
        m = red_minute[side]
        return 0.0 if m is None else (90 - m) / 90

    h_exp, h_conv = chances_and_conversion(hs.attack * hm, as_.defence * am, poss_home)
    a_exp, a_conv = chances_and_conversion(as_.attack * am, hs.defence * hm, 1 - poss_home)
    h_exp *= (1 - TEN_MEN_ATTACK * man_down("home")) * (1 + TEN_MEN_DEFENCE * man_down("away"))
    a_exp *= (1 - TEN_MEN_ATTACK * man_down("away")) * (1 + TEN_MEN_DEFENCE * man_down("home"))

    for side, xi, opp_xi, exp, conv in (
        ("home", home_xi, away_xi, h_exp, h_conv),
        ("away", away_xi, home_xi, a_exp, a_conv),
    ):
        if not xi:
            continue
        keeper = _keeper(opp_xi)
        keeper_name = keeper.name if keeper else "the defender in goal"
        for _ in range(poisson(exp, rng)):
            minute = rng.randint(1, 90)
            shooter = _pick_shooter(on_pitch(xi, minute), rng)
            roll = rng.random()
            if roll < conv:
                kind = "goal"
            else:
                kind = rng.choices(["saved", "miss", "post"], weights=[50, 38, 12])[0]
            events.append(MatchEvent(minute, side, kind, shooter.name, keeper_name, shooter.id))
            if kind == "goal":
                if side == "home":
                    result.home_goals += 1
                else:
                    result.away_goals += 1

        for p in xi:
            if rng.random() < 0.012:
                minute = rng.randint(1, 90)
                if sent_off.get(p.id, 999) <= minute:
                    continue
                weeks = rng.randint(1, 5)
                result.injuries.append([p.id, weeks])
                events.append(MatchEvent(minute, side, "injury", p.name, "", p.id))

    for side, xi in (("home", home_xi), ("away", away_xi)):
        if not xi:
            continue
        for _ in range(poisson(DECISIONS_PER_TEAM, rng)):
            minute = rng.randint(1, 90)
            players = on_pitch(xi, minute)
            outfield = [p for p in players if p.pos != "GK"] or players
            detail = rng.choices(DECISIONS, weights=DECISION_WEIGHTS)[0]
            who = _pick_shooter(players, rng) if detail in ("offside", "penalty") else rng.choice(outfield)
            events.append(MatchEvent(minute, side, "decision", who.name, "", who.id, detail))

    events.sort(key=lambda e: e.minute)
    result.events = events

    if cup and result.home_goals == result.away_goals:
        hp, ap = penalty_shootout(home_xi, away_xi, rng, hm, am)
        result.pens = f"{hp}-{ap}"
    return result


def penalty_shootout(
    a_xi: list[Player], b_xi: list[Player], rng: random.Random, a_boost=1.0, b_boost=1.0
) -> tuple[int, int]:
    """Returns (a, b) penalties scored. The stronger side is a little more likely to win."""
    a_ov, b_ov = team_strength(a_xi).overall * a_boost, team_strength(b_xi).overall * b_boost
    a_wins = rng.random() < 0.5 + (a_ov - b_ov) / 200
    win = rng.randint(3, 5)
    lose = rng.randint(max(0, win - 3), win - 1)
    return (win, lose) if a_wins else (lose, win)
