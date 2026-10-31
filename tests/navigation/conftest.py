import json
import shutil
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI

from bussola.api.state import AppState
from tests.apiclient import ApiClient, Json

FAKE_SERVER = Path(__file__).parent.parent / "fakelsp" / "fake-language-server"
WAIT_SECONDS = 15.0
POLL_SECONDS = 0.05


class LanguageServerPath:
    def __init__(self, bin_dir: Path, state: Path, log: Path) -> None:
        self.bin_dir = bin_dir
        self.state = state
        self.log = log

    def install(self, name: str, **state: Any) -> None:
        self.state.write_text(json.dumps(state))
        script = self.bin_dir / name
        script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE_SERVER}" "$@"\n')
        script.chmod(0o755)

    def messages(self) -> list[dict[str, Any]]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def environment(self) -> dict[str, str | None]:
        return json.loads(self.log.with_suffix(".env.json").read_text())

    def methods(self) -> list[str]:
        return [message["method"] for message in self.messages() if "method" in message]


@pytest.fixture(autouse=True)
def servers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LanguageServerPath:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = shutil.which("git")
    assert git is not None
    (bin_dir / "git").symlink_to(git)
    state, log = tmp_path / "lsp-state.json", tmp_path / "lsp-log.jsonl"
    state.write_text("{}")
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("FAKE_LSP_STATE", str(state))
    monkeypatch.setenv("FAKE_LSP_LOG", str(log))
    return LanguageServerPath(bin_dir, state, log)


@pytest.fixture
def nav_api(api: ApiClient) -> Iterator[ApiClient]:
    yield api
    cast(AppState, cast(FastAPI, api.client.app).state.bussola).navigator.close()


def wait_for(probe: Callable[[], Json], done: Callable[[Json], bool]) -> Json:
    deadline = time.monotonic() + WAIT_SECONDS
    result = probe()
    while not done(result):
        assert time.monotonic() < deadline, f"Gave up waiting, last result: {result}"
        time.sleep(POLL_SECONDS)
        result = probe()
    return result
