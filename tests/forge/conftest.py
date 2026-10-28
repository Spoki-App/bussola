import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.gitrepo import GitFixture

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


GITHUB_URL = "git@github.com:acme/widgets.git"
BASE = "def total(items):\n    return 0\n"
FIRST = "def total(items):\n    return sum(items)\n"
SECOND = "def total(items):\n    return sum(items, 0)\n"


class GitHubSandbox:
    def __init__(self, local: GitFixture, contributor: GitFixture, fake_gh: FakeGh) -> None:
        self.local = local
        self.contributor = contributor
        self.fake_gh = fake_gh

    def open_pull_request(self, files: dict[str, str], state: str = "OPEN", base: str = "main") -> str:
        head = self.contributor.commit(files, "contribution")
        self.contributor.git("push", "-q", "--force", "origin", "HEAD:refs/pull/7/head")
        pull = {
            "number": 7,
            "title": "Sum the items",
            "url": "https://github.com/acme/widgets/pull/7",
            "headRefOid": head,
            "headRefName": "sum-items",
            "baseRefName": base,
            "author": {"login": "bob"},
            "state": state,
            "isDraft": False,
            "body": "Sums the items instead of returning zero.\n\n- [x] tested",
            "comments": {"totalCount": 2},
            "reviewThreads": {"nodes": [{"isResolved": False, "comments": {"totalCount": 3}}, {"isResolved": True, "comments": {"totalCount": 1}}]},
        }
        self.fake_gh.configure(prs=[pull], files=[])
        return head


@pytest.fixture
def github(tmp_path: Path, git_repo: GitFixture, fake_gh: FakeGh) -> GitHubSandbox:
    bare = tmp_path / "widgets.git"
    GitFixture(tmp_path).git("init", "-q", "--bare", "-b", "main", str(bare))
    git_repo.commit({"app.py": BASE}, "base")
    git_repo.git("remote", "add", "origin", GITHUB_URL)
    git_repo.git("config", f"url.{bare}.insteadOf", GITHUB_URL)
    git_repo.git("push", "-q", "origin", "main")
    contributor = GitFixture(tmp_path / "contributor")
    GitFixture(tmp_path).git("clone", "-q", str(bare), str(contributor.root))
    contributor.git("config", "user.email", "bob@example.com")
    contributor.git("config", "user.name", "Bob")
    contributor.git("checkout", "-q", "-b", "sum-items")
    return GitHubSandbox(git_repo, contributor, fake_gh)
