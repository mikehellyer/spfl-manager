from spfl_manager import __version__, updater


def test_version_comparison():
    assert updater.is_newer("v0.8.0", "0.7.0")
    assert updater.is_newer("0.7.1", "0.7.0")
    assert not updater.is_newer("v0.7.0", "0.7.0")
    assert not updater.is_newer("0.6.9", "0.7.0")
    assert updater.parse_version(__version__) >= (0, 7, 0)


def test_pick_installer_for_each_platform():
    assets = [
        {"name": "SPFL-Manager-0.8.0-macOS.dmg", "url": "mac"},
        {"name": "SPFL-Manager-0.8.0-Windows-Setup.exe", "url": "win"},
        {"name": "spfl-manager_0.8.0_amd64.deb", "url": "deb"},
    ]
    assert updater.pick_installer(assets, "darwin") == "mac"
    assert updater.pick_installer(assets, "win32") == "win"
    assert updater.pick_installer(assets, "linux") == "deb"
    assert updater.pick_installer([], "linux") == ""
