"""Build the native installer for the computer this runs on.

    .venv/bin/python tools/build.py

macOS   -> dist/SPFL-Manager-<version>-macOS.dmg        (drag to Applications)
Windows -> dist/SPFL-Manager-<version>-Windows-Setup.exe (Start Menu + optional desktop icon)
Linux   -> dist/spfl-manager_<version>_amd64.deb        (menu entry + icon)

GitHub Actions runs this on all three when a version tag is pushed
(see .github/workflows/release.yml). Needs PyInstaller (requirements-dev.txt),
plus Inno Setup on Windows and dpkg-deb on Linux.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spfl_manager import APP_NAME, __version__  # noqa: E402

DIST = ROOT / "dist"
PACK = ROOT / "packaging"
SYSTEM = platform.system()  # Darwin / Windows / Linux


def run(cmd: list, **kw):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def freeze():
    """PyInstaller: bundle Python, pygame, the game code and its data files."""
    sep = ";" if os.name == "nt" else ":"
    icon = {"Darwin": "icon.icns", "Windows": "icon.ico"}.get(SYSTEM, "icon.png")
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--name",
            APP_NAME,
            "--paths",
            "src",
            "--icon",
            str(PACK / icon),
            "--add-data",
            f"src/spfl_manager/assets{sep}spfl_manager/assets",
            "--add-data",
            f"src/spfl_manager/core/squads.json{sep}spfl_manager/core",
            "--osx-bundle-identifier",
            "com.mikehellyer.spflmanager",
            "main.py",
        ],
        cwd=ROOT,
    )


def set_mac_version(app: Path):
    """PyInstaller leaves the app's version as 0.0.0 - set the real one (shown in Finder)."""
    import plistlib

    plist = app / "Contents" / "Info.plist"
    info = plistlib.loads(plist.read_bytes())
    info["CFBundleShortVersionString"] = __version__
    info["CFBundleVersion"] = __version__
    info["NSHumanReadableCopyright"] = "MIT licence - github.com/mikehellyer/spfl-manager"
    plist.write_bytes(plistlib.dumps(info))
    # Changing Info.plist breaks PyInstaller's signature, and macOS refuses to open an app
    # whose signature doesn't match - so sign it again (ad hoc) and check it verifies.
    run(["codesign", "--force", "--deep", "--sign", "-", app])
    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", app])


def build_mac() -> Path:
    app = DIST / f"{APP_NAME}.app"
    set_mac_version(app)
    stage = DIST / "dmg"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir()
    shutil.copytree(app, stage / app.name, symlinks=True)
    (stage / "Applications").symlink_to("/Applications")
    out = DIST / f"SPFL-Manager-{__version__}-macOS.dmg"
    out.unlink(missing_ok=True)
    run(["hdiutil", "create", "-volname", APP_NAME, "-srcfolder", stage, "-ov", "-format", "UDZO", out])
    shutil.rmtree(stage)
    return out


def find_iscc() -> str:
    for candidate in (
        shutil.which("iscc"),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ):
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("Inno Setup (ISCC.exe) not found - install it with: choco install innosetup")


def build_windows() -> Path:
    run([find_iscc(), f"/DAppVersion={__version__}", str(PACK / "installer.iss")])
    return DIST / f"SPFL-Manager-{__version__}-Windows-Setup.exe"


def build_deb() -> Path:
    pkg = "spfl-manager"
    root = DIST / "deb"
    shutil.rmtree(root, ignore_errors=True)
    opt = root / "opt" / pkg
    shutil.copytree(DIST / APP_NAME, opt, symlinks=True)

    (root / "usr" / "bin").mkdir(parents=True)
    launcher = root / "usr" / "bin" / pkg
    launcher.write_text(f'#!/bin/sh\nexec "/opt/{pkg}/{APP_NAME}" "$@"\n')
    launcher.chmod(0o755)

    apps = root / "usr" / "share" / "applications"
    apps.mkdir(parents=True)
    (apps / f"{pkg}.desktop").write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "Comment=Scottish football management - a tribute to C64 Football Manager 2\n"
        f"Exec={pkg}\n"
        f"Icon={pkg}\n"
        "Terminal=false\n"
        "Categories=Game;SportsGame;\n"
    )
    icons = root / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    icons.mkdir(parents=True)
    from PIL import Image

    Image.open(PACK / "icon.png").resize((256, 256), Image.NEAREST).save(icons / f"{pkg}.png")

    size_kb = sum(f.stat().st_size for f in root.rglob("*") if f.is_file()) // 1024
    (root / "DEBIAN").mkdir()
    (root / "DEBIAN" / "control").write_text(
        f"Package: {pkg}\n"
        f"Version: {__version__}\n"
        "Section: games\n"
        "Priority: optional\n"
        "Architecture: amd64\n"
        f"Installed-Size: {size_kb}\n"
        "Maintainer: Mike Hellyer <https://github.com/mikehellyer/spfl-manager>\n"
        "Homepage: https://github.com/mikehellyer/spfl-manager\n"
        "Description: Scottish football management game\n"
        " A modern tribute to the classic C64 Football Manager 2, set in the SPFL\n"
        " from the Premiership down to League Two.\n"
    )
    out = DIST / f"{pkg}_{__version__}_amd64.deb"
    run(["dpkg-deb", "--build", "--root-owner-group", root, out])
    shutil.rmtree(root)
    return out


def main():
    freeze()
    out = {"Darwin": build_mac, "Windows": build_windows, "Linux": build_deb}[SYSTEM]()
    print(f"\nBuilt {out}  ({out.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
