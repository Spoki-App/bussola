from pathlib import Path

import pytest

from tests.apiclient import ApiClient
from tests.gitrepo import GitFixture


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    for name in ("beta", "Alpha", ".hidden"):
        (root / name).mkdir(parents=True)
    GitFixture.create(root / "project")
    (root / "notes.txt").write_text("not a directory")
    return root


def test_lists_visible_subdirectories_sorted_and_marks_repositories(api: ApiClient, workspace: Path) -> None:
    listing = api.call("GET", f"/directories?path={workspace}")

    assert [(entry["name"], entry["is_repo"]) for entry in listing["entries"]] == [("Alpha", False), ("beta", False), ("project", True)]
    assert listing["path"] == str(workspace.resolve())
    assert listing["parent"] == str(workspace.resolve().parent)
    assert listing["is_repo"] is False


def test_repository_directory_reports_itself_as_repository(api: ApiClient, workspace: Path) -> None:
    listing = api.call("GET", f"/directories?path={workspace / 'project'}")

    assert listing["is_repo"] is True


def test_defaults_to_the_home_directory(api: ApiClient) -> None:
    listing = api.call("GET", "/directories")

    assert listing["path"] == str(Path.home().resolve())
    assert listing["home"] == listing["path"]


def test_missing_path_and_files_are_rejected(api: ApiClient, workspace: Path) -> None:
    missing = api.call("GET", f"/directories?path={workspace / 'nope'}", 400)
    file = api.call("GET", f"/directories?path={workspace / 'notes.txt'}", 400)

    assert "does not exist" in missing["detail"]
    assert "not a directory" in file["detail"]


def test_filesystem_root_has_no_parent(api: ApiClient) -> None:
    assert api.call("GET", "/directories?path=/")["parent"] is None
