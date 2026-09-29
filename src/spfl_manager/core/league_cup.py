"""The Scottish League Cup (Premier Sports Cup), 2026-27 format.

Group stage (July, before the league): 40 clubs - the 37 SPFL clubs not in
Europe plus three non-league clubs (Highland League champions and runners-up,
Lowland League champions) - in eight groups of five, seeded from five pots by
last season's league positions. Every club plays the other four once. A win is
3 points; every draw goes straight to penalties: 2 points for the shoot-out
winner, 1 for the loser.

The eight group winners and the three best runners-up join the five clubs in
European competition in the second round. The Europeans and the three best
group winners are seeded. From then on it's knock-out (extra time and
penalties), with the semi-finals and final at Hampden.

Competition state (saved in the game) is a plain dict - see new_competition().
"""

from __future__ import annotations

import random

from .fixtures import round_robin

NAME = "League Cup"
GROUP_NAMES = "ABCDEFGH"
MATCHDAYS = 5  # five clubs per group: four games each and one week off
# knock-out rounds: (name, played after this league week)
KO_ROUNDS = [("Second Round", 2), ("Quarter-Final", 7), ("Semi-Final", 13), ("Final", 19)]
NEUTRAL_ROUNDS = {2, 3}  # semi-finals and final at Hampden
PRIZE = [25_000, 50_000, 100_000, 300_000]  # for winning each knock-out round

# The real 2026-27 draw (27 May 2026) and European entrants.
REAL_2026_GROUPS = [
    ["Aberdeen", "Queen's Park", "Queen of the South", "Kelty Hearts", "Brora Rangers"],
    ["Dundee United", "Arbroath", "Montrose", "The Spartans", "Stirling Albion"],
    ["St Mirren", "Dunfermline Athletic", "Cove Rangers", "East Kilbride", "Dumbarton"],
    ["Dundee", "Airdrieonians", "Ross County", "Clyde", "Annan Athletic"],
    ["Livingston", "Partick Thistle", "Stenhousemuir", "Forfar Athletic", "Brechin City"],
    ["St Johnstone", "Greenock Morton", "Inverness CT", "East Fife", "Linlithgow Rose"],
    ["Falkirk", "Ayr United", "Alloa Athletic", "Stranraer", "Edinburgh City"],
    ["Kilmarnock", "Raith Rovers", "Peterhead", "Hamilton Academical", "Elgin City"],
]
REAL_2026_EUROPE = ["Celtic", "Heart of Midlothian", "Rangers", "Motherwell", "Hibernian"]
REAL_2026_NON_LEAGUE = ["Linlithgow Rose", "Brora Rangers", "Brechin City"]


def label_group(matchday: int) -> str:
    return f"{NAME} Group Matchday {matchday + 1}"


def label_round(idx: int) -> str:
    return f"{NAME} {KO_ROUNDS[idx][0]}"


def event_rounds(league_week: int) -> list[int]:
    """Knock-out rounds played after this league week (1-based)."""
    return [i for i, (_, week) in enumerate(KO_ROUNDS) if week == league_week]


def empty_row() -> dict:
    return {"P": 0, "W": 0, "PW": 0, "PL": 0, "L": 0, "F": 0, "A": 0, "Pts": 0}


def _group_fixtures(groups: list[list[str]], rng: random.Random) -> list[list[list[str]]]:
    """Five matchdays; on each, two games per group (one club rests)."""
    days: list[list[list[str]]] = [[] for _ in range(MATCHDAYS)]
    for teams in groups:
        order = list(teams)
        rng.shuffle(order)
        pos = {t: i for i, t in enumerate(order)}
        for md, rnd in enumerate(round_robin(order)):
            for a, b in rnd:
                # each club hosts the next two clubs round the circle: exactly 2 home, 2 away
                home_first = (pos[b] - pos[a]) % 5 in (1, 2)
                days[md].append([a, b] if home_first else [b, a])
    return days


def new_competition(groups: list[list[str]], europe: list[str], ratings: dict, rng: random.Random) -> dict:
    return {
        "stage": "groups",  # groups -> knockout -> done
        "groups": groups,
        "tables": {team: empty_row() for g in groups for team in g},
        "fixtures": _group_fixtures(groups, rng),
        "matchday": 0,
        "europe": list(europe),
        "ratings": dict(ratings),  # non-league clubs' strength
        "round": 0,  # next knock-out round
        "ties": [],
        "winner": "",
        "out": False,
    }


def draw_groups(ranked: list[str], rng: random.Random) -> list[list[str]]:
    """40 clubs in seeding order -> eight groups, one club from each of five pots."""
    pots = [ranked[i : i + 8] for i in range(0, 40, 8)]
    groups: list[list[str]] = [[] for _ in range(8)]
    for pot in pots:
        pot = list(pot)
        rng.shuffle(pot)
        for g, team in enumerate(pot):
            groups[g].append(team)
    return groups


def record_group_result(state: dict, home: str, away: str, hg: int, ag: int, pens: str):
    t = state["tables"]
    for team, gf, ga in ((home, hg, ag), (away, ag, hg)):
        row = t[team]
        row["P"] += 1
        row["F"] += gf
        row["A"] += ga
        if gf > ga:
            row["W"] += 1
            row["Pts"] += 3
        elif gf < ga:
            row["L"] += 1
    if hg == ag and pens:  # shoot-out: 2 points to the winner, 1 to the loser
        ph, pa = (int(x) for x in pens.split("-"))
        winner, loser = (home, away) if ph > pa else (away, home)
        t[winner]["PW"] += 1
        t[winner]["Pts"] += 2
        t[loser]["PL"] += 1
        t[loser]["Pts"] += 1


def _key(state, team):
    r = state["tables"][team]
    return (-r["Pts"], -(r["F"] - r["A"]), -r["F"], -r["W"], team)


def standings(state: dict, group: int) -> list[str]:
    return sorted(state["groups"][group], key=lambda t: _key(state, t))


def finish_groups(state: dict, rng: random.Random) -> tuple[list[str], list[str]]:
    """Returns (qualifiers, seeded) and makes the second-round draw."""
    winners = [standings(state, g)[0] for g in range(8)]
    runners = [standings(state, g)[1] for g in range(8)]
    best_runners = sorted(runners, key=lambda t: _key(state, t))[:3]
    best_winners = sorted(winners, key=lambda t: _key(state, t))[:3]
    seeded = state["europe"] + best_winners
    unseeded = [t for t in winners + best_runners if t not in seeded]
    rng.shuffle(seeded)
    rng.shuffle(unseeded)
    ties = []
    for s, u in zip(seeded, unseeded):
        ties.append([s, u] if rng.random() < 0.5 else [u, s])
    state["ties"] = ties
    state["stage"] = "knockout"
    return winners + best_runners, seeded


def alive(state: dict) -> set:
    """Clubs still involved (for keeping non-league squads around)."""
    if not state:
        return set()
    if state.get("stage") == "groups":
        return {t for g in state["groups"] for t in g}
    return {t for tie in state.get("ties", []) for t in tie}
