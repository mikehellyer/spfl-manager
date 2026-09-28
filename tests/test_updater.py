from spfl_manager import __version__, updater


def test_version_comparison():
    assert updater.is_newer("v0.8.0", "0.7.0")
    assert updater.is_newer("0.7.1", "0.7.0")
    assert not updater.is_newer("v0.7.0", "0.7.0")
    assert not updater.is_newer("0.6.9", "0.7.0")
    assert updater.parse_version(__version__) >= (0, 7, 0)
