import plistlib
import subprocess
import sys
import webbrowser
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

CHROME_APPS_DIR = Path.home() / "Applications" / "Chrome Apps.localized"
INFO_PLIST = Path("Contents") / "Info.plist"
APP_ID_KEY = "CrAppModeShortcutID"
APP_URL_KEY = "CrAppModeShortcutURL"
BROWSER_BUNDLE_KEY = "CrBundleIdentifier"
PROFILE_DIR_KEY = "CrAppModeUserDataDir"
WEB_APPLICATIONS_DIR = "Web Applications"
UNKNOWN_PROFILE = "-"

Runner = Callable[[Sequence[str]], bool]


@dataclass(frozen=True)
class ChromeApp:
    app_id: str
    browser_bundle: str
    profile: str | None


def installed_app(url: str, apps_dir: Path = CHROME_APPS_DIR) -> ChromeApp | None:
    origin = _origin(url)
    if origin is None or not apps_dir.is_dir():
        return None
    for bundle in sorted(apps_dir.glob("*.app")):
        info = _read_info(bundle / INFO_PLIST)
        if info is None or _origin(info.get(APP_URL_KEY)) != origin:
            continue
        app_id, browser = info.get(APP_ID_KEY), info.get(BROWSER_BUNDLE_KEY)
        if isinstance(app_id, str) and app_id and isinstance(browser, str) and browser:
            return ChromeApp(app_id, browser, _profile(info.get(PROFILE_DIR_KEY)))
    return None


def app_command(app: ChromeApp, url: str) -> list[str]:
    profile = [f"--profile-directory={app.profile}"] if app.profile else []
    return ["open", "-n", "-b", app.browser_bundle, "--args", *profile, f"--app-id={app.app_id}", f"--app-launch-url-for-shortcuts-menu-item={url}"]


def open_url(url: str, apps_dir: Path = CHROME_APPS_DIR, run: Runner | None = None, browser: Callable[[str], bool] = webbrowser.open) -> bool:
    app = installed_app(url, apps_dir) if sys.platform == "darwin" else None
    if app is not None and (run or _run)(app_command(app, url)):
        return True
    return browser(url)


def _run(command: Sequence[str]) -> bool:
    try:
        return subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0
    except OSError:
        return False


def _read_info(path: Path) -> dict[str, Any] | None:
    try:
        info = plistlib.loads(path.read_bytes())
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None
    return cast(dict[str, Any], info) if isinstance(info, dict) else None


def _origin(url: object) -> tuple[str, str, int | None] | None:
    if not isinstance(url, str):
        return None
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    return parts.scheme, parts.hostname, port


def _profile(user_data_dir: object) -> str | None:
    if not isinstance(user_data_dir, str):
        return None
    parts = Path(user_data_dir).parts
    if WEB_APPLICATIONS_DIR not in parts:
        return None
    index = parts.index(WEB_APPLICATIONS_DIR)
    profile = parts[index - 1] if index > 0 else UNKNOWN_PROFILE
    return None if profile == UNKNOWN_PROFILE else profile
