import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

FAKE_GH_DIR = Path(__file__).parent.parent / "fakegh"


class FakeGh:
    def __init__(self, state_path: Path, log_path: Path) -> None:
        self.state_path = state_path
        self.log_path = log_path

    def configure(self, **state: Any) -> None:
        current = json.loads(self.state_path.read_text())
        current.update(state)
        self.state_path.write_text(json.dumps(current))

    def calls(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text().splitlines()]

    def api_posts(self, fragment: str) -> list[dict[str, Any]]:
        return [call for call in self.calls() if call["args"][0] == "api" and any(fragment in arg for arg in call["args"]) and call["input"] is not None]

    def clear_log(self) -> None:
        self.log_path.unlink(missing_ok=True)


@pytest.fixture
def fake_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeGh:
    state = tmp_path / "gh-state.json"
    state.write_text(json.dumps({"authenticated": True, "prs": [], "files": [], "next_id": 1000, "review_comments": {}}))
    log = tmp_path / "gh-log.jsonl"
    monkeypatch.setenv("FAKE_GH_STATE", str(state))
    monkeypatch.setenv("FAKE_GH_LOG", str(log))
    monkeypatch.setenv("PATH", f"{FAKE_GH_DIR}{os.pathsep}{os.environ['PATH']}")
    return FakeGh(state, log)


@pytest.fixture
def without_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = shutil.which("git")
    assert git is not None
    (bin_dir / "git").symlink_to(git)
    monkeypatch.setenv("PATH", str(bin_dir))
