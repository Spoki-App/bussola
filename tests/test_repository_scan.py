from pathlib import Path

import pytest

from rtool.directories import ScanLimits, find_repositories
from tests.apiclient import ApiClient
from tests.gitrepo import GitFixture


@pytest.fixture
def home(tmp_path: Path) -> Path:
    root = tmp_path / "home"
    GitFixture.create(root / "Projects" / "shop")
    GitFixture.create(root / "Projects" / "shop" / "plugins" / "nested")
    GitFixture.create(root / "work" / "clients" / "acme" / "api")
    GitFixture.create(root / "a" / "b" / "c" / "d" / "too-deep")
    GitFixture.create(root / ".config" / "hidden-repo")
    GitFixture.create(root / "web" / "node_modules" / "left-pad")
    (root / "Documents" / "notes").mkdir(parents=True)
    return root


def test_finds_repositories_without_entering_them(home: Path) -> None:
    scan = find_repositories(home)

    assert [repo.path for repo in scan.repositories] == [str(home / "Projects" / "shop"), str(home / "work" / "clients" / "acme" / "api")]
    assert scan.truncated is False


def test_skips_hidden_and_dependency_folders_and_respects_depth(home: Path) -> None:
    names = {repo.name for repo in find_repositories(home).repositories}

    assert names.isdisjoint({"hidden-repo", "left-pad", "too-deep", "nested"})
    assert "too-deep" in {repo.name for repo in find_repositories(home, ScanLimits(max_depth=6)).repositories}


def test_stops_at_the_result_limit(home: Path) -> None:
    scan = find_repositories(home, ScanLimits(max_results=1))

    assert len(scan.repositories) == 1
    assert scan.truncated is True


def test_does_not_follow_symlinks(home: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    GitFixture.create(outside / "linked-repo")
    (home / "link").symlink_to(outside, target_is_directory=True)

    assert "linked-repo" not in {repo.name for repo in find_repositories(home).repositories}


def test_api_marks_repositories_already_added(api: ApiClient, git_repo: GitFixture, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    git_repo.commit({"a.txt": "a\n"})
    monkeypatch.setenv("HOME", str(tmp_path))
    other = GitFixture.create(tmp_path / "other")
    other.commit({"b.txt": "b\n"})
    api.call("POST", "/repos", 201, {"path": str(git_repo.root)})

    scan = api.call("GET", "/directories/repositories")

    flags = {repo["name"]: repo["registered"] for repo in scan["repositories"]}
    assert flags == {"repo": True, "other": False}
