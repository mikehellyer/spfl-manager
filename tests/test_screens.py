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
    pygame.quit()
