from pathlib import Path

import pytest

from tests.gitrepo import GitFixture


@pytest.fixture
def git_repo(tmp_path: Path) -> GitFixture:
    return GitFixture.create(tmp_path / "repo")
