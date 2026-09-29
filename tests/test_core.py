import random
from collections import Counter

from spfl_manager.core import data
from spfl_manager.core.database import SquadDB
from spfl_manager.core.fixtures import league_schedule, round_robin
from spfl_manager.core.game import Game
from spfl_manager.core.match import simulate_match
from spfl_manager.core.models import team_strength


def test_round_robin_everyone_meets_once():
    teams = [f"T{i}" for i in range(10)]
    rounds = round_robin(teams)
    assert len(rounds) == 9
    pairs = Counter(frozenset(p) for r in rounds for p in r)
    assert len(pairs) == 45 and set(pairs.values()) == {1}
    for r in rounds:
        playing = [t for p in r for t in p]
        assert len(playing) == len(set(playing)) == 10


def test_league_schedule_lengths():
    rng = random.Random(1)
    assert len(league_schedule([str(i) for i in range(12)], 3, rng)) == 33
    sched = league_schedule([str(i) for i in range(10)], 4, rng)
    assert len(sched) == 36
    homes = Counter(h for r in sched for h, _ in r)
    assert set(homes.values()) == {18}


def test_divisions_sizes():
    assert [len(d) for d in data.CLUBS] == [12, 10, 10, 10]


def test_new_game_setup():
    g = Game.new("Mike", "Stranraer", seed=3, db=SquadDB.load_default())
    assert sum(1 for c in g.clubs.values() if c.division < 4) == 42
    assert g.club.division == 3
    assert all(len(g.squad(c)) >= 12 for c in g.clubs)
    assert len(g.club.selected) == 11
    # Preliminary Round One: 45 non-league clubs, 5 ties and 35 byes (2026-27 format)
    assert len(g.cup["ties"]) == 5 and len(g.cup["byes"]) == 35


def test_strength_formation_tradeoff():
    g = Game.new("Mike", "Clyde", seed=4)
    squad = g.squad("Clyde")
    for p in squad:
        p.skill, p.energy = 50, 100
    gk = [p for p in squad if p.pos == "GK"][:1]
    dfs = [p for p in squad if p.pos == "DEF"]
    mids = [p for p in squad if p.pos == "MID"]
    atts = [p for p in squad if p.pos == "ATT"]
    s442 = team_strength(gk + dfs[:4] + mids[:4] + atts[:2])
    assert abs(s442.defence - 50) < 2 and abs(s442.midfield - 50) < 2 and abs(s442.attack - 50) < 2
    s541 = team_strength(gk + dfs[:5] + mids[:4] + atts[:1])
    assert s541.defence > s442.defence and s541.attack < s442.attack


def test_match_is_deterministic_and_plausible():
    g = Game.new("Mike", "Clyde", seed=5)
    a, b = g.selected_players("Celtic"), g.selected_players("Clyde")
    r1 = simulate_match("Celtic", "Clyde", a, b, random.Random(9))
    r2 = simulate_match("Celtic", "Clyde", a, b, random.Random(9))
    assert (r1.home_goals, r1.away_goals) == (r2.home_goals, r2.away_goals)
    rng = random.Random(10)
    celtic_wins = sum(simulate_match("Celtic", "Clyde", a, b, rng).winner == "Celtic" for _ in range(200))
    assert celtic_wins > 150


def test_cup_ties_go_to_penalties():
    g = Game.new("Mike", "Clyde", seed=6)
    a, b = g.selected_players("Dumbarton"), g.selected_players("Clyde")
    rng = random.Random(1)
    for _ in range(100):
        r = simulate_match("Dumbarton", "Clyde", a, b, rng, cup=True)
        assert r.winner in ("Dumbarton", "Clyde")


def test_full_season_and_promotion():
    g = Game.new("Mike", "Hibernian", seed=7)
    summary = None
    goals = matches = 0
    while summary is None:
        rep = g.play_week()
        for r in rep.results:
            goals += r.home_goals + r.away_goals
            matches += 1
        summary = rep.season_summary
    assert 1.8 < goals / matches < 4.0
    assert 3 <= len(summary["promoted"]) <= 7 and len(summary["promoted"]) == len(summary["relegated"])
    assert [len(d) for d in g.divisions] == [12, 10, 10, 10]
    assert g.cup["winner"] == "" and g.week == 0 and g.season == 2027
    assert summary["cup_winner"]
    assert all(len(g.squad(c)) >= 12 for c in g.clubs)


def test_save_round_trip(tmp_path):
    g = Game.new("Mike", "Forfar Athletic", seed=8)
    for _ in range(3):
        g.play_week()
    path = tmp_path / "save.json"
    g.save(path)
    h = Game.load(path)
    assert h.to_dict() == g.to_dict()
    assert h.play_week().label == g.play_week().label


def test_transfers():
    g = Game.new("Mike", "Forfar Athletic", seed=9)
    g.balance = 10_000_000
    pid, asking = g.market[0]
    ok, _ = g.bid(pid, asking * 2)
    assert ok and g.players[pid].club == "Forfar Athletic"
    seller_offer = g.sale_offer(pid)
    buyer, fee = seller_offer
    g.accept_sale(pid, buyer, fee)
    assert g.players[pid].club == buyer


def test_real_squads_loaded():
    g = Game.new("Mike", "Elgin City", seed=12)
    names = {p.name for p in g.squad("Elgin City")}
    assert {"Kane Hester", "Russell Dingwall", "Tom Ritchie"} <= names
    assert g.club.division == 3 and g.club.pattern == "stripes"
    assert sum(1 for p in g.squad("Elgin City") if p.pos == "GK") >= 2
    dingwall = next(p for p in g.squad("Elgin City") if p.name == "Russell Dingwall")
    assert dingwall.age == 29  # born 26 June 1997, age on 1 July 2026


def test_league_lineup_matches_squad_file():
    from spfl_manager.core.database import SquadDB

    real = SquadDB.load_default().clubs
    for div in data.CLUBS:
        for c in div:
            assert c.name in real, c.name


def test_estimates_are_stable_and_overrides_win(tmp_path):
    db = SquadDB.load_default()
    rec = next(r for r in db.squad("Elgin City") if r["name"] == "Kane Hester")
    first = db.stats("Elgin City", rec)
    assert first == db.stats("Elgin City", rec)
    assert first[2] and first[3]  # skill and age both estimated
    rec["skill"], rec["age"] = 55, 30
    assert db.stats("Elgin City", rec)[:4] == (55, 30, False, False)
    assert db.stats("Elgin City", rec, season=2028)[1] == 32

    db.ratings["Elgin City"] = 60
    path = tmp_path / "squads.json"
    db.save(path)
    loaded = SquadDB.load(path)
    assert loaded.custom and loaded.rating("Elgin City") == 60
    g = Game.new("Mike", "Elgin City", seed=1, db=loaded)
    hester = next(p for p in g.squad("Elgin City") if p.name == "Kane Hester")
    assert (hester.skill, hester.age) == (55, 30)
    assert g.club.rating == 60


def test_editor_moves_and_reset(tmp_path):
    db = SquadDB.load_default()
    rec = db.squad("Elgin City")[0]
    db.move_player(rec, "Elgin City", "Clyde")
    assert rec in db.squad("Clyde") and rec not in db.squad("Elgin City")
    path = tmp_path / "squads.json"
    db.save(path)
    fresh = SquadDB.reset(path)
    assert not path.exists() and not fresh.custom
    assert any(r["name"] == rec["name"] for r in fresh.squad("Elgin City"))


def test_save_game_editing():
    g = Game.new("Mike", "Elgin City", seed=2, db=SquadDB.load_default())
    edit = g.copy()
    hester = next(p for p in edit.squad("Elgin City") if p.name == "Kane Hester")
    hester.skill = 70
    assert (
        next(p for p in g.squad("Elgin City") if p.name == "Kane Hester").skill != 70
    )  # copy is independent
    picked = edit.club.selected[0]
    assert edit.move_player(picked, "Clyde") == ""
    assert picked not in edit.club.selected and edit.players[picked].club == "Clyde"
    new = edit.add_player("Elgin City", "Mike Hellyer", "ATT", 60, 25)
    assert new.id in edit.players and new.id not in g.players
    while len(edit.squad("Stranraer")) > 13:
        assert edit.remove_player(edit.squad("Stranraer")[0].id) == ""
    assert edit.remove_player(edit.squad("Stranraer")[0].id) != ""  # refuses to go below 13
    for _ in range(3):
        edit.play_week()  # still plays fine after edits


def _play_to_playoffs(g):
    while g.playoff_week() is None:
        g.play_week()


def test_playoffs_structure_and_movement():
    g = Game.new("Mike", "Hibernian", seed=21, db=SquadDB.load_default())
    _play_to_playoffs(g)
    finals = [[n for n, _ in g.table(d)] for d in range(4)]
    summary = None
    while summary is None:
        summary = g.play_week().season_summary
    # (can't inspect g.playoffs any more - a new season has started - so check the outcome)
    assert [len(d) for d in g.divisions] == [12, 10, 10, 10]
    assert len(summary["playoffs"]) == 4
    assert finals[0][11] in g.divisions[1] and finals[1][0] in g.divisions[0]
    assert finals[3][0] in g.divisions[2] and finals[2][9] in g.divisions[3]
    # the Premiership's 11th either stayed up or was replaced by a Championship play-off club
    prem_line = next(line for line in summary["playoffs"] if line.startswith("Premiership"))
    winner = prem_line.split(": ")[1].split(" beat ")[0]
    assert winner in g.divisions[0]
    assert winner == finals[0][10] or winner in finals[1][1:4]


def test_pyramid_club_can_replace_league_two_bottom():

    g = Game.new("Mike", "Celtic", seed=22, db=SquadDB.load_default())
    _play_to_playoffs(g)
    bottom = g.table(3)[-1][0]
    g._ensure_playoffs()
    challenger = g.playoffs["entrant"]
    assert g.position(challenger) == 0  # non-league clubs have no SPFL position (used to crash)
    for p in g.squad(challenger):
        p.skill = 99  # make sure the Highland/Lowland side wins
    for p in g.squad(bottom):
        p.skill = 5
    summary = None
    while summary is None:
        summary = g.play_week().season_summary
    assert challenger in g.divisions[3] and bottom not in g.clubs
    assert not any(p.club == bottom for p in g.players.values())
    assert [len(d) for d in g.divisions] == [12, 10, 10, 10]
    g.play_week()  # new season runs with the newcomers


def test_manager_dropping_out_of_spfl_ends_game():
    g = Game.new("Mike", "Elgin City", seed=23, db=SquadDB.load_default())
    _play_to_playoffs(g)
    # rig it: Elgin bottom of League Two, and the challenger is unbeatable
    g.tables["Elgin City"]["Pts"] = -100
    g._ensure_playoffs()
    for p in g.squad(g.playoffs["entrant"]):
        p.skill = 99
    for p in g.squad("Elgin City"):
        p.skill = 5
    summary = None
    while summary is None:
        summary = g.play_week().season_summary
    assert summary.get("dropped_out") and g.sacked and "SPFL" in g.game_over_reason


def test_old_save_without_playoffs_still_loads(tmp_path):
    g = Game.new("Mike", "Elgin City", seed=24, db=SquadDB.load_default())
    d = g.to_dict()
    d.pop("playoffs")
    d.pop("game_over_reason")
    h = Game.from_dict(d)
    assert h.playoffs == {} and h.calendar[-1] == ["playoff", 5]


def test_long_career_stays_healthy():
    """Several seasons in: squads refill, divisions stay the right size, pyramid pool never runs dry."""
    g = Game.new("Mike", "Celtic", seed=33, db=SquadDB.load_default())
    for _ in range(4):
        summary = None
        while summary is None:
            summary = g.play_week().season_summary
        assert [len(d) for d in g.divisions] == [12, 10, 10, 10]
        assert all(len(g.squad(c)) >= 18 for c in g.clubs if g.clubs[c].division < 4)
        assert len([c for c in g.non_league if c["name"] not in g.clubs]) >= 2
    assert Game.from_dict(g.to_dict()).to_dict() == g.to_dict()


def test_premiership_split():
    g = Game.new("Mike", "Hibernian", seed=41, db=SquadDB.load_default())
    while not (g._event()[0] == "league" and g._event()[1] == 33):
        g.play_week()
    assert all(g.tables[c]["P"] == 33 for c in g.divisions[0])
    top_after_33 = [n for n, _ in g.table(0)][:6]
    g.play_week()
    top = list(g.split["top"])
    assert top == top_after_33
    assert len(g.fixtures[0]) == 38
    for rnd in g.fixtures[0][33:]:
        for h, a in rnd:
            assert (h in top) == (a in top)  # nobody plays across the split
    summary = None
    finals_top = None
    while summary is None:
        if g.week == len(g.calendar) - 1:
            finals_top = [n for n, _ in g.table(0)][:6]
            assert sorted(finals_top) == sorted(top)  # the halves never cross
            prem_p = {c: g.tables[c]["P"] for c in g.divisions[0]}
            lower_p = {c: g.tables[c]["P"] for d in (1, 2, 3) for c in g.divisions[d]}
        summary = g.play_week().season_summary
    assert set(prem_p.values()) == {38} and set(lower_p.values()) == {36}


def test_premiership_playoff_final_uses_final_11th():
    g = Game.new("Mike", "Hibernian", seed=42, db=SquadDB.load_default())
    eleventh = None
    while g.playoff_week() is None or g.playoff_week() < 2:
        g.play_week()
    eleventh = g.table(0)[10][0]
    summary = None
    while summary is None:
        summary = g.play_week().season_summary
    line = next(entry for entry in summary["playoffs"] if entry.startswith("Premiership"))
    assert eleventh in line


def test_decisions_are_flavour_only():
    g = Game.new("Mike", "Clyde", seed=61, db=SquadDB.load_default())
    a, b = g.selected_players("Dumbarton"), g.selected_players("Clyde")
    rng = random.Random(3)
    seen = set()
    for _ in range(200):
        r = simulate_match("Dumbarton", "Clyde", a, b, rng)
        goals = [e for e in r.events if e.kind == "goal"]
        assert len(goals) == r.home_goals + r.away_goals
        seen |= {e.detail for e in r.events if e.kind == "decision"}
    assert seen == {"offside", "penalty", "free_kick", "booking"}


def lcup_alive(g):
    from spfl_manager.core import league_cup

    return league_cup.alive(g.league_cup)


def _play_season(g):
    rounds, summary = {}, None
    while summary is None:
        rep = g.play_week()
        for name, results in rep.cup_rounds:
            if name.startswith("Scottish Cup "):
                rounds[name.replace("Scottish Cup ", "")] = results
        summary = rep.season_summary
    return rounds, summary


def test_scottish_cup_follows_the_official_format():
    from spfl_manager.core import data

    # a Premiership manager, so the season can't end early with the club dropping out of the SPFL
    g = Game.new("Mike", "Hibernian", seed=91, db=SquadDB.load_default())
    divisions = [set(d) for d in g.divisions]
    rounds, summary = _play_season(g)
    assert {name: len(res) for name, res in rounds.items()} == {
        "Preliminary Round One": 5,
        "Preliminary Round Two": 20,
        "Preliminary Round Three": 10,
        "First Round": 30,
        "Second Round": 20,
        "Third Round": 20,
        "Fourth Round": 16,
        "Fifth Round": 8,
        "Quarter-Final": 4,
        "Semi-Final": 2,
        "Final": 1,
    }

    def first_round(clubs):
        for i, (name, *_rest) in enumerate(data.CUP_ROUNDS):
            if {t for r in rounds[name] for t in (r.home, r.away)} & clubs:
                return i
        return None

    # League Two enter in Round Two, League One and the Championship in Round Three,
    # and the Premiership in Round Four
    assert first_round(divisions[3]) == 4
    assert first_round(divisions[2] | divisions[1]) == 5
    assert first_round(divisions[0]) == 6
    spfl = set().union(*divisions)
    for name in ("Preliminary Round One", "Preliminary Round Two", "Preliminary Round Three", "First Round"):
        assert not any({r.home, r.away} & spfl for r in rounds[name])
    assert summary["cup_winner"]
    # every non-league cup side has gone home - only the new season's three League Cup
    # entrants are around
    assert sum(1 for c in g.clubs.values() if c.division < 4) == 42
    assert {n for n, c in g.clubs.items() if c.division == 4} <= lcup_alive(g)


def test_non_league_opponent_exists_from_the_draw_until_the_week_after():
    g = Game.new("Mike", "Elgin City", seed=93, db=SquadDB.load_default())
    while g.cup["round"] < 4:  # up to the Round Two draw, when League Two enter
        g.play_week()
    spfl = {c for d in g.divisions for c in d}
    mixed = [(h, a) for h, a in g.cup["ties"] if (h in spfl) != (a in spfl)]
    assert mixed  # some League Two clubs have drawn non-league sides
    assert all(h in g.clubs and a in g.clubs for h, a in mixed)  # squads ready for pre-match
    while g._event()[0] != "cup":
        g.play_week()
    rep = g.play_week()  # Round Two
    for res in rep.cup_rounds[0][1]:
        if res.home in spfl or res.away in spfl:
            assert res.home in g.clubs and res.away in g.clubs  # still there for the results screen
    g.play_week()
    alive = set(g.cup["remaining"]) | set(g.cup["byes"]) | {t for x in g.cup["ties"] for t in x}
    assert all(c.division < 4 or n in alive for n, c in g.clubs.items())  # the beaten ones went home


def test_legacy_save_moves_onto_the_new_cup():
    g = Game.new("Mike", "Elgin City", seed=92, db=SquadDB.load_default())
    for _ in range(3):
        g.play_week()
    d = g.to_dict()
    # what a v0.9 save looked like at the same point: old calendar index 3, old-style cup
    d["cup"] = {"round": 0, "ties": [["Clyde", "Stranraer"]], "byes": ["Celtic"], "winner": "", "out": False}
    d["week"] = 3
    for newer in ("calendar", "league_cup", "europe", "prev_order"):  # a v0.9 save had none of these
        d.pop(newer)
    h = Game.from_dict(d)
    assert "remaining" in h.cup
    assert h.calendar[h.week] == ["league", 3]
    assert h.cup["round"] == 1  # Preliminary Round One (league week 1) has been caught up
    for _ in range(12):
        h.play_week()
    assert h.cup["round"] >= 5


def test_league_cup_follows_the_2026_27_format():
    from spfl_manager.core import league_cup as lc

    g = Game.new("Mike", "Elgin City", seed=101, db=SquadDB.load_default())
    st = g.league_cup
    # season one uses the real draw: Elgin in Group H
    assert st["groups"][7] == ["Kilmarnock", "Raith Rovers", "Peterhead", "Hamilton Academical", "Elgin City"]
    assert set(st["europe"]) == {"Celtic", "Heart of Midlothian", "Rangers", "Motherwell", "Hibernian"}
    assert sum(len(gr) for gr in st["groups"]) == 40
    # the group stage comes first, before the league
    assert [ev[0] for ev in g.calendar[:5]] == ["lcup_group"] * 5
    rounds = {}
    while g.league_cup.get("stage") != "done":
        rep = g.play_week()
        for name, results in rep.cup_rounds:
            if name.startswith("League Cup"):
                rounds[name] = results
    tables = g.league_cup["tables"]
    for row in tables.values():
        assert row["P"] == 4
        # points: 3 per win, 2 per shoot-out win, 1 per shoot-out loss
        assert row["Pts"] == 3 * row["W"] + 2 * row["PW"] + row["PL"]
        assert row["W"] + row["PW"] + row["PL"] + row["L"] == 4
    for md in range(5):
        games = rounds[f"League Cup Group Matchday {md + 1}"]
        assert len(games) == 16
    home_games = {}
    for md in range(5):
        for r in rounds[f"League Cup Group Matchday {md + 1}"]:
            home_games[r.home] = home_games.get(r.home, 0) + 1
    assert len(home_games) == 40 and set(home_games.values()) == {2}  # two home, two away each
    r2 = rounds["League Cup Second Round"]
    assert len(r2) == 8
    in_r2 = {t for r in r2 for t in (r.home, r.away)}
    assert {"Celtic", "Heart of Midlothian", "Rangers", "Motherwell", "Hibernian"} <= in_r2
    assert len(rounds["League Cup Quarter-Final"]) == 4
    assert len(rounds["League Cup Semi-Final"]) == 2
    assert len(rounds["League Cup Final"]) == 1
    assert g.league_cup["winner"] == rounds["League Cup Final"][0].winner
    assert g.cup_neutral("League Cup Semi-Final") and g.cup_neutral("League Cup Final")
    assert not g.cup_neutral("League Cup Quarter-Final")
    # the final is in December (after league week 19), long before the end of the season
    assert lc.KO_ROUNDS[-1][1] == 19


def test_next_season_europe_and_league_cup_draw():
    g = Game.new("Mike", "Hibernian", seed=102, db=SquadDB.load_default())
    summary = None
    while summary is None:
        rep = g.play_week()
        summary = rep.season_summary
    assert summary["league_cup_winner"]
    assert len(g.europe) == 5 and len(set(g.europe)) == 5
    assert g.europe[:4] == g.prev_order[:4]  # top four in the Premiership
    st = g.league_cup  # the new season's competition
    assert sum(len(gr) for gr in st["groups"]) == 40
    teams = {t for gr in st["groups"] for t in gr}
    assert not teams & set(g.europe)
    non_league = [t for t in teams if g.clubs[t].division == 4]
    assert len(non_league) == 3


def test_v010_save_gets_the_league_cup():
    g = Game.new("Mike", "Elgin City", seed=103, db=SquadDB.load_default())
    d = g.to_dict()
    # a v0.10 save at League Week 4: no calendar, no League Cup, v0.10 calendar indexes
    from spfl_manager.core.game import calendar_v10

    old = calendar_v10()
    d["week"] = old.index(["league", 3])
    for newer in ("calendar", "league_cup", "europe", "prev_order"):
        d.pop(newer)
    h = Game.from_dict(d)
    assert h.calendar[h.week] == ["league", 3]
    st = h.league_cup
    assert st["stage"] == "knockout" and st["round"] == 1  # groups and Second Round caught up
    assert any("League Cup" in n for n in h.news)
    for _ in range(40):
        if h.league_cup["stage"] == "done":
            break
        h.play_week()
    assert h.league_cup["stage"] == "done" and h.league_cup["winner"]
