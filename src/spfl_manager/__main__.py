import sys
from pathlib import Path


def self_test(report_path: str = "") -> int:
    """Check a packaged build has everything it needs. Exit code 0 = OK.

    Used by tools/build.py and CI:  "SPFL Manager" --self-test [report.txt]
    """
    lines, ok = [], True
    try:
        from . import __version__
        from .core.database import SquadDB
        from .core.game import Game
        from .ui.sound import ASSETS, CROWD_FILES

        db = SquadDB.load_default()
        players = sum(len(v) for v in db.clubs.values())
        lines.append(f"version {__version__}: {len(db.clubs)} clubs, {players} real players")
        ok &= len(db.clubs) == 42 and players > 1000
        missing = [f for f in CROWD_FILES if not (ASSETS / f"{f}.wav").exists()]
        import certifi

        certs = Path(certifi.where()).exists()
        lines.append(f"HTTPS certificates for the update check: {'bundled' if certs else 'MISSING'}")
        ok &= certs
        icon = Path(ASSETS).parent / "icon.png"
        lines.append(f"sounds missing: {missing or 'none'}; icon: {icon.exists()}")
        ok &= not missing and icon.exists()
        g = Game.new("Self Test", "Elgin City", seed=1, db=db)
        report = g.play_week()
        lines.append(f"played {report.label}: {len(report.results)} results")
    except Exception as exc:  # report anything, never crash silently
        lines.append(f"FAILED: {exc!r}")
        ok = False
    lines.append("SELF-TEST " + ("PASSED" if ok else "FAILED"))
    text = "\n".join(lines)
    print(text)  # no-op in a windowed build without a console
    if report_path:
        Path(report_path).write_text(text + "\n")
    return 0 if ok else 1


def check_update_report(report_path: str = "") -> int:
    """Diagnostics: can this build reach GitHub and see the latest release? Exit code 0 = yes."""
    from . import __version__, updater

    try:
        release = updater.latest_release(timeout=10)
        tag = release.get("tag_name", "?")
        text = f"This is v{__version__}. Latest release on GitHub: {tag}."
        text += " An update is available." if updater.is_newer(tag) else " You're up to date."
        code = 0
    except Exception as exc:
        text, code = f"Update check FAILED: {exc!r}", 1
    print(text)
    if report_path:
        Path(report_path).write_text(text + "\n")
    return code


def main():
    if "--check-update" in sys.argv:
        i = sys.argv.index("--check-update")
        sys.exit(check_update_report(sys.argv[i + 1] if len(sys.argv) > i + 1 else ""))
    if "--self-test" in sys.argv:
        i = sys.argv.index("--self-test")
        sys.exit(self_test(sys.argv[i + 1] if len(sys.argv) > i + 1 else ""))

    from .ui.app import App
    from .ui.intro import BootScene

    app = App()
    app.run(BootScene(app))


if __name__ == "__main__":
    main()
