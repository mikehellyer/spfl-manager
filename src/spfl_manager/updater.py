"""Update checker: polls GitHub Releases in the background and only *notifies*.

Nothing is ever downloaded or installed automatically - the player has to
choose "Update" from the main menu, which opens the release page.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import urllib.request

from . import __version__

# The GitHub repo whose Releases are checked for newer versions.
GITHUB_REPO = "mikehellyer/spfl-manager"


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def is_newer(latest: str, current: str = __version__) -> bool:
    return parse_version(latest) > parse_version(current)


def check_for_update(timeout: float = 5.0) -> dict | None:
    if not GITHUB_REPO:
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        release = json.load(resp)
    tag = release.get("tag_name", "")
    if tag and is_newer(tag):
        assets = [{"name": a["name"], "url": a["browser_download_url"]} for a in release.get("assets", [])]
        return {
            "version": tag.lstrip("v"),
            "url": release.get("html_url", ""),
            "notes": release.get("body", ""),
            "download": pick_installer(assets),
        }
    return None


def pick_installer(assets: list[dict], platform: str = sys.platform) -> str:
    """The download link for this computer's installer ('' if there isn't one)."""
    suffix = ".dmg" if platform == "darwin" else ".exe" if platform.startswith("win") else ".deb"
    return next((a["url"] for a in assets if a["name"].lower().endswith(suffix)), "")


def check_async(callback) -> None:
    def worker():
        try:
            info = check_for_update()
        except Exception:
            return  # offline or GitHub unavailable - stay quiet
        if info:
            callback(info)

    threading.Thread(target=worker, daemon=True).start()
