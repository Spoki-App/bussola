from pathlib import Path

import pytest

from tests.apiclient import ApiClient
from tests.gitrepo import GitFixture


@pytest.fixture
def git_repo(tmp_path: Path) -> GitFixture:
    return GitFixture.create(tmp_path / "repo")


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "data"
    monkeypatch.setenv("RTOOL_DATA_DIR", str(path))
    return path


@pytest.fixture
def api(git_repo: GitFixture, data_dir: Path) -> ApiClient:
    return ApiClient.create(git_repo, data_dir)
