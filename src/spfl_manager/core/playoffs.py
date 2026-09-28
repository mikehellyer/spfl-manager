"""SPFL promotion/relegation play-offs (all ties over two legs).

Premiership play-off:  Championship 3rd v 4th (QF), winner v Championship 2nd (SF),
                       winner v Premiership 11th (final).
Championship play-off: Championship 9th v League One 4th, League One 2nd v 3rd, then a final.
League One play-off:   League One 9th v League Two 4th, League Two 2nd v 3rd, then a final.
League Two play-off:   League Two 10th v the Highland/Lowland League play-off winner.

Each tie is a dict: side "a" is at home in the first leg, side "b" (the better
seed) is at home in the second leg. A side can be "?" until an earlier tie is won.
"""

from __future__ import annotations

PLAYOFF_WEEKS = 6

COMP_NAMES = {
    "prem": "Premiership play-off",
    "champ": "Championship play-off",
    "l1": "League One play-off",
    "l2": "League Two play-off",
}


def _tie(key, comp, rnd, a, b, weeks, a_from="", b_from="", stay=""):
    return {
        "key": key,
        "comp": comp,
        "round": rnd,
        "a": a,
        "b": b,
        "weeks": weeks,
        "a_from": a_from,
        "b_from": b_from,
        "stay": stay,  # the higher-division club defending its place (finals only)
        "legs": [],
        "winner": "",
        "loser": "",
        "note": "",
    }


def create(tables: list[list[str]], entrant: str) -> dict:
    """tables: final league positions per division (index 0 = top)."""
    prem, champ, l1, l2 = tables  # prem may be None while the Premiership is still playing
    ties = [
        _tie("prem_qf", "prem", "Quarter-final", champ[3], champ[2], [0, 1]),
        _tie("prem_sf", "prem", "Semi-final", "?", champ[1], [2, 3], a_from="prem_qf"),
        _tie(
            "prem_f",
            "prem",
            "Final",
            "?",
            prem[10] if prem else "?",
            [4, 5],
            a_from="prem_sf",
            stay=prem[10] if prem else "",
        ),
        _tie("champ_sf1", "champ", "Semi-final", l1[3], champ[8], [0, 1]),
        _tie("champ_sf2", "champ", "Semi-final", l1[2], l1[1], [0, 1]),
        _tie(
            "champ_f",
            "champ",
            "Final",
            "?",
            "?",
            [2, 3],
            a_from="champ_sf2",
            b_from="champ_sf1",
            stay=champ[8],
        ),
        _tie("l1_sf1", "l1", "Semi-final", l2[3], l1[8], [0, 1]),
        _tie("l1_sf2", "l1", "Semi-final", l2[2], l2[1], [0, 1]),
        _tie("l1_f", "l1", "Final", "?", "?", [2, 3], a_from="l1_sf2", b_from="l1_sf1", stay=l1[8]),
        _tie("l2_f", "l2", "Final", entrant, l2[9], [2, 3], stay=l2[9]),
    ]
    return {"ties": ties, "entrant": entrant}


def tie_name(tie: dict) -> str:
    return f"{COMP_NAMES[tie['comp']]} {tie['round']}"


def fixtures(po: dict, week: int) -> list[tuple[dict, int, str, str]]:
    """(tie, leg, home, away) for every leg played in this play-off week."""
    out = []
    for t in po.get("ties", []):
        if week in t["weeks"] and "?" not in (t["a"], t["b"]) and not t["winner"]:
            leg = t["weeks"].index(week)
            home, away = (t["a"], t["b"]) if leg == 0 else (t["b"], t["a"])
            out.append((t, leg, home, away))
    return out


def aggregate(tie: dict) -> tuple[int, int]:
    """Goals for (a, b) over the legs played so far."""
    a = b = 0
    for i, (hg, ag) in enumerate(tie["legs"]):
        if i == 0:
            a, b = a + hg, b + ag
        else:
            a, b = a + ag, b + hg
    return a, b


def record_leg(po: dict, tie: dict, home_goals: int, away_goals: int, shootout=None) -> str:
    """Store a leg's score. After the second leg, decide the tie and return a news line.

    `shootout` is called with no arguments when the aggregate is level and must
    return (a_pens, b_pens).
    """
    tie["legs"].append([home_goals, away_goals])
    if len(tie["legs"]) < 2:
        return ""
    a, b = aggregate(tie)
    if a == b:
        pa, pb = shootout()
        winner, loser = (tie["a"], tie["b"]) if pa > pb else (tie["b"], tie["a"])
        tie["note"] = f"{a}-{b} on aggregate, {max(pa, pb)}-{min(pa, pb)} on penalties"
    else:
        winner, loser = (tie["a"], tie["b"]) if a > b else (tie["b"], tie["a"])
        tie["note"] = f"{max(a, b)}-{min(a, b)} on aggregate"
    tie["winner"], tie["loser"] = winner, loser
    for t in po["ties"]:
        if t["a_from"] == tie["key"]:
            t["a"] = winner
        if t["b_from"] == tie["key"]:
            t["b"] = winner
    return f"{tie_name(tie)}: {winner} beat {loser} {tie['note']}."


def get(po: dict, key: str) -> dict | None:
    return next((t for t in po.get("ties", []) if t["key"] == key), None)


def leg_label(tie: dict, leg: int, short=lambda name: name) -> str:
    """e.g. 'League One play-off Final, 2nd leg (1st leg ELG 0-4 KEL)'."""
    label = f"{tie_name(tie)}, {'1st' if leg == 0 else '2nd'} leg"
    if leg == 1 and tie["legs"]:
        hg, ag = tie["legs"][0]
        label += f" (1st leg {short(tie['a'])} {hg}-{ag} {short(tie['b'])})"
    return label
