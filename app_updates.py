"""Crew Manager update check (Jerry's design, 2026-10-22,
confirmed 2026-10-26 with GitHub as the host).

The app carries its own version. At most once a day it
fetches a tiny version.json from the project's GitHub
repo and, when a newer release exists, the main window
shows a dismissible banner. Nothing is ever downloaded
or installed automatically - the banner's button opens
the release page and the user takes it from there.
Offline or a broken feed fails silently: no error, no
banner, try again tomorrow.

The repo is the public update channel ONLY (README,
version.json, Release assets) - no source lives there,
so the feed must be readable without any login.
"""

import json
import os
import urllib.request
from datetime import date

CURRENT_VERSION = "1.0.0"

# Filled in when the GitHub repo exists (Jerry's account).
REPO = "ControlWorks/Crew-Manager-Releases"
FEED_URL = ("https://raw.githubusercontent.com/%s/main/"
            "version.json" % REPO) if REPO else ""
RELEASES_URL = ("https://github.com/%s/releases"
                % REPO) if REPO else ""

STATE_NAME = "crew_manager_update.json"


def parse_version(text):
    """'1.2.3' -> (1, 2, 3); junk -> None."""
    try:
        parts = [p for p in
                 str(text).strip().lstrip("v").split(".")
                 if p != ""]
        if not parts:
            return None
        return tuple(int(p) for p in parts)
    except (TypeError, ValueError):
        return None


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    if a is None or b is None:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def default_state_path():
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        STATE_NAME)


def load_state(path=None):
    try:
        with open(path or default_state_path(),
                  encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state, path=None):
    try:
        with open(path or default_state_path(), "w",
                  encoding="utf-8") as f:
            json.dump(state, f, indent=1)
    except OSError:
        pass  # state is a nicety, never a blocker


def fetch_latest(url, timeout=4, opener=None):
    """GET the feed and parse it; None on ANY failure."""
    try:
        if opener is not None:
            raw = opener(url, timeout)
        else:
            req = urllib.request.Request(
                url, headers={"User-Agent": "CrewManager"})
            with urllib.request.urlopen(
                    req, timeout=timeout) as resp:
                raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict) \
                or not parse_version(data.get("latest")):
            return None
        return {"version": str(data["latest"]),
                "url": str(data.get("url") or ""),
                "notes": str(data.get("notes") or "")}
    except Exception:
        return None


def check_for_update(feed_url=None, state_path=None,
                     today=None, fetcher=None,
                     current=CURRENT_VERSION):
    """Return {"version", "url", "notes"} when a newer,
    not-dismissed release exists; otherwise None.

    At most one fetch per day: the attempt is stamped
    into the state file whether it succeeds or not, and
    a same-day call returns None without fetching.
    Tests inject feed_url/fetcher/today/state_path.
    """
    url = FEED_URL if feed_url is None else feed_url
    if not url:
        return None  # no repo configured yet
    today = today or date.today().isoformat()
    state = load_state(state_path)
    if state.get("last_check") == today:
        return None
    info = (fetcher or fetch_latest)(url)
    state["last_check"] = today
    save_state(state, state_path)
    if not info:
        return None
    if not is_newer(info["version"], current):
        return None
    if state.get("dismissed") == info["version"]:
        return None
    if not info["url"]:
        info["url"] = RELEASES_URL
    return info


def dismiss(version, state_path=None):
    state = load_state(state_path)
    state["dismissed"] = version
    save_state(state, state_path)
