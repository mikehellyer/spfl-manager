import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest


@pytest.fixture(autouse=True)
def isolated_user_data(tmp_path, monkeypatch):
    """Never read or write the real ~/.spfl_manager folder from tests."""
    from spfl_manager.core import database

    monkeypatch.setattr(database, "user_file", lambda: tmp_path / "user" / "squads.json")
