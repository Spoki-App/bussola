import shutil
from pathlib import Path

from tests.apiclient import ApiClient
from tests.gitrepo import GitFixture


def test_unknown_branch_is_a_clear_client_error(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"a.txt": "a\n"})
    repo = api.call("POST", "/repos", 201, {"path": str(git_repo.root)})

    error = api.call("POST", f"/repos/{repo['id']}/reviews", 400, {"head_ref": "nope", "base_ref": "main"})

    assert "nope" in error["detail"]
    assert "code" not in error


def test_refresh_after_branch_deletion_reports_the_missing_ref(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"a.txt": "a\n"})
    git_repo.branch("feature")
    git_repo.commit({"a.txt": "b\n"})
    review = api.start_review()
    git_repo.checkout("main")
    git_repo.git("branch", "-D", "feature")

    error = api.call("POST", f"/reviews/{review}/refresh", 400, {"fetch": False})

    assert "feature" in error["detail"]


def test_moved_repository_is_found_again_by_its_first_commit(api: ApiClient, git_repo: GitFixture, tmp_path: Path) -> None:
    git_repo.commit({"a.txt": "a\n"})
    git_repo.branch("feature")
    git_repo.commit({"a.txt": "b\n"})
    review = api.start_review()
    moved = tmp_path / "moved"
    shutil.move(git_repo.root, moved)

    missing = api.call("GET", "/repos")[0]
    stale = api.call("POST", f"/reviews/{review}/refresh", 409, {"fetch": False})
    relinked = api.call("POST", "/repos", 201, {"path": str(moved)})

    assert missing["missing"] is True
    assert "Register it again" in stale["detail"]
    assert relinked["id"] == missing["id"]
    assert relinked["path"] == str(moved.resolve())
    assert api.call("GET", f"/reviews/{review}")["total"] == 1


def test_path_that_is_not_a_repository_is_rejected(api: ApiClient, tmp_path: Path) -> None:
    error = api.call("POST", "/repos", 400, {"path": str(tmp_path)})

    assert "not a git repository" in error["detail"]


def test_unreachable_remote_falls_back_to_the_local_branch_with_a_warning(api: ApiClient, git_repo: GitFixture, tmp_path: Path) -> None:
    git_repo.commit({"a.txt": "a\n"})
    git_repo.git("remote", "add", "origin", str(tmp_path / "missing.git"))
    git_repo.branch("feature")
    git_repo.commit({"a.txt": "b\n"})
    review = api.start_review()
    git_repo.commit({"a.txt": "c\n"})

    result = api.call("POST", f"/reviews/{review}/refresh", body={"fetch": True})

    assert result["created"] is True
    assert result["warning"].startswith("Could not fetch")
