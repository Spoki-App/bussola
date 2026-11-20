import plistlib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from bussola.handler.chrome_app import ChromeApp, app_command, installed_app, open_url

APP_ID = "ndclgahegldohknijikipmikgfefalhe"
REVIEW_URL = "http://127.0.0.1:8765/reviews/7?token=secret"


def install(apps_dir: Path, name: str, **info: Any) -> None:
    contents = apps_dir / f"{name}.app" / "Contents"
    contents.mkdir(parents=True)
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))


def bussola_app(apps_dir: Path, url: str = "http://127.0.0.1:8765/", user_data_dir: str = "/Chrome/-/Web Applications/_crx_x") -> None:
    install(
        apps_dir,
        "bussola",
        CrAppModeShortcutID=APP_ID,
        CrAppModeShortcutURL=url,
        CrBundleIdentifier="com.google.Chrome",
        CrAppModeUserDataDir=user_data_dir,
    )


def test_the_app_installed_for_the_origin_of_the_url_is_found(tmp_path: Path) -> None:
    install(tmp_path, "GitHub", CrAppModeShortcutID="other", CrAppModeShortcutURL="https://github.com/", CrBundleIdentifier="com.google.Chrome")
    bussola_app(tmp_path)

    assert installed_app(REVIEW_URL, tmp_path) == ChromeApp(APP_ID, "com.google.Chrome", None)


@pytest.mark.parametrize("url", ["http://127.0.0.1:8766/", "http://localhost:8765/", "https://127.0.0.1:8765/"])
def test_an_app_installed_for_another_port_host_or_scheme_is_not_used(tmp_path: Path, url: str) -> None:
    bussola_app(tmp_path, url)

    assert installed_app(REVIEW_URL, tmp_path) is None


def test_a_broken_bundle_or_a_missing_folder_finds_no_app(tmp_path: Path) -> None:
    broken = tmp_path / "broken.app" / "Contents"
    broken.mkdir(parents=True)
    (broken / "Info.plist").write_text("not a plist")
    truncated = tmp_path / "truncated.app" / "Contents"
    truncated.mkdir(parents=True)
    (truncated / "Info.plist").write_text('<?xml version="1.0"?><plist version="1.0"><dict><key>CrAppModeShortcutID</key>')

    assert installed_app(REVIEW_URL, tmp_path) is None
    assert installed_app(REVIEW_URL, tmp_path / "missing") is None


def test_the_profile_of_the_app_is_read_from_its_data_folder(tmp_path: Path) -> None:
    bussola_app(tmp_path, user_data_dir="/Users/me/Library/Application Support/Google/Chrome/Profile 2/Web Applications/_crx_x")

    assert installed_app(REVIEW_URL, tmp_path) == ChromeApp(APP_ID, "com.google.Chrome", "Profile 2")


def test_the_browser_opens_the_app_on_the_url() -> None:
    assert app_command(ChromeApp(APP_ID, "com.google.Chrome", "Profile 2"), REVIEW_URL) == [
        "open",
        "-n",
        "-b",
        "com.google.Chrome",
        "--args",
        "--profile-directory=Profile 2",
        f"--app-id={APP_ID}",
        f"--app-launch-url-for-shortcuts-menu-item={REVIEW_URL}",
    ]


@pytest.mark.skipif(sys.platform != "darwin", reason="Chrome app bundles are a macOS feature")
def test_a_url_with_an_installed_app_opens_in_the_app(tmp_path: Path) -> None:
    bussola_app(tmp_path)
    commands: list[Sequence[str]] = []
    tabs: list[str] = []

    opened = open_url(REVIEW_URL, tmp_path, run=lambda command: commands.append(command) is None, browser=lambda url: tabs.append(url) is None)

    assert opened
    assert commands == [app_command(ChromeApp(APP_ID, "com.google.Chrome", None), REVIEW_URL)]
    assert tabs == []


@pytest.mark.skipif(sys.platform != "darwin", reason="Chrome app bundles are a macOS feature")
def test_a_url_opens_in_a_tab_when_the_app_cannot_be_opened(tmp_path: Path) -> None:
    bussola_app(tmp_path)
    tabs: list[str] = []

    assert open_url(REVIEW_URL, tmp_path, run=lambda _command: False, browser=lambda url: tabs.append(url) is None)
    assert tabs == [REVIEW_URL]


def test_a_url_without_an_installed_app_opens_in_a_tab(tmp_path: Path) -> None:
    commands: list[Sequence[str]] = []
    tabs: list[str] = []

    assert open_url(REVIEW_URL, tmp_path, run=lambda command: commands.append(command) is None, browser=lambda url: tabs.append(url) is None)
    assert (commands, tabs) == ([], [REVIEW_URL])
