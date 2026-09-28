"""Fixture generation (round robin) and cup draws."""

from __future__ import annotations

import random


def round_robin(teams: list[str]) -> list[list[tuple[str, str]]]:
    """Single round robin using the circle method. Returns a list of rounds."""
    teams = list(teams)
    if len(teams) % 2:
        teams.append(None)
    n = len(teams)
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = teams[i], teams[n - 1 - i]
            if a is None or b is None:
                continue
            # alternate home advantage so nobody gets a long run of home games
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        rounds.append(pairs)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return rounds


def league_schedule(teams: list[str], cycles: int, rng: random.Random) -> list[list[list[str]]]:
    """Play everyone `cycles` times, swapping home/away each cycle."""
    order = list(teams)
    rng.shuffle(order)
    base = round_robin(order)
    schedule = []
    for c in range(cycles):
        for rnd in base:
            if c % 2 == 0:
                schedule.append([[h, a] for h, a in rnd])
            else:
                schedule.append([[a, h] for h, a in rnd])
    return schedule


def cup_draw(teams: list[str], rng: random.Random) -> list[list[str]]:
    pool = list(teams)
    rng.shuffle(pool)
    return [[pool[i], pool[i + 1]] for i in range(0, len(pool) - 1, 2)]
