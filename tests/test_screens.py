"""Draw every screen once (headless) - catches crashes such as a missing setting."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")


def test_every_management_screen_draws(tmp_path, monkeypatch):
    from spfl_manager.core import game as gm
    from spfl_manager.core.database import SquadDB
    from spfl_manager.ui import editor, hub, screens
    from spfl_manager.ui.app import App

    save = tmp_path / "savegame.json"
    for module in (gm, screens, hub, editor):
        monkeypatch.setattr(module, "save_path", lambda: save, raising=False)

    app = App()
    g = gm.Game.new("Test", "Elgin City", seed=5, db=SquadDB.load_default())
    app.game = g
    app.push(hub.HubScene(app))
    for _ in range(12):  # into the cup season, so cup pages have something to show
        report = g.play_week()
    scenes = [
        hub.HubScene(app),
        screens.SquadScene(app),
        screens.TableScene(app),
        screens.FixturesScene(app),
        screens.MarketScene(app),
        screens.FinanceScene(app),
        screens.NewsScene(app),
        screens.PreMatchScene(app),
        screens.ResultsScene(app, report),
        editor.EditorScene(app),
        editor.EditorScene(app, editor.SaveBackend(app)),
    ]
    for scene in scenes:
        scene.update(1 / 60)
        scene.draw(app.canvas)
    league_cup_page = screens.TableScene(app)
    league_cup_page.div = 4  # the League Cup groups page
    league_cup_page.draw(app.canvas)
    results = screens.ResultsScene(app, report)
    for page in range(results.pages):
        results.page = page
        results.draw(app.canvas)
    from spfl_manager.ui import records

    stats_page = records.StatsScene(app)
    g.history.append(
        {"season": "2025/26", "club": "Elgin City", "division": "SPFL League Two", "position": 3}
    )
    for _ in records.PAGES:
        stats_page.draw(app.canvas)
        stats_page.turn(1)
    pygame.quit()


def test_intro_survives_an_update_being_found(tmp_path, monkeypatch):
    """v0.9.1-v0.14.0 crashed on the loading screen whenever GitHub had a newer version."""
    from spfl_manager import updater
    from spfl_manager.ui import intro
    from spfl_manager.ui import theme as T
    from spfl_manager.ui.app import App

    monkeypatch.setattr(T, "_fonts", {})  # fonts from an earlier test die with its pygame.quit()
    monkeypatch.setattr(updater, "check_async", lambda callback: None)
    monkeypatch.setattr(intro, "save_path", lambda: tmp_path / "savegame.json")
    app = App()
    app.push(intro.BootScene(app))
    info = {"version": "99.0.0", "url": "", "notes": "", "download": ""}
    for frame in range(400):  # the whole loading screen and on into the title screen
        if frame == 30:
            app.update_info = info  # the background check answers mid-load
        app.scene.update(1 / 60)
        app.scene.draw(app.canvas)
    assert isinstance(app.scene, intro.TitleScene)
    assert "UPDATE TO v99.0.0" in [item[0] for item in app.scene.menu.items]

    # ...and one that answers after the title screen is already up
    app.update_info = None
    title = intro.TitleScene(app)
    app.update_info = info
    title.update(1 / 60)
    assert "UPDATE TO v99.0.0" in [item[0] for item in title.menu.items]
    pygame.quit()
