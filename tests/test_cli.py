from pathlib import Path

import pytest
from typer.testing import CliRunner

from bussola.cli import app
from tests.gitrepo import GitFixture

runner = CliRunner()


def test_status_prints_unit_states(git_repo: GitFixture, data_dir: Path) -> None:
    git_repo.commit({"app.py": "def f():\n    return 1\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": "def f():\n    return 2\n"})

    result = runner.invoke(app, ["status", "feature", "--repo", str(git_repo.root)])

    assert result.exit_code == 0, result.output
    assert result.output.split() == ["new", "function", "app.py::f"]
    assert (data_dir / "bussola.db").is_file()


@pytest.mark.usefixtures("data_dir")
def test_status_uses_bussola_toml_base_branch(git_repo: GitFixture) -> None:
    git_repo.commit({".bussola.toml": 'base_branch = "trunk"\n', "a.txt": "a\n"})
    git_repo.branch("trunk")
    git_repo.branch("feature")
    git_repo.commit({"a.txt": "b\n"})

    result = runner.invoke(app, ["status", "feature", "--repo", str(git_repo.root)])

    assert result.exit_code == 0, result.output
    assert result.output.split() == ["new", "file", "a.txt"]


@pytest.mark.usefixtures("data_dir")
def test_refresh_reports_new_and_unchanged_revisions(git_repo: GitFixture) -> None:
    git_repo.commit({"a.txt": "a\n"})
    git_repo.branch("feature")
    git_repo.commit({"a.txt": "b\n"})
    arguments = ["refresh", "feature", "--base", "main", "--repo", str(git_repo.root)]

    first = runner.invoke(app, arguments)
    second = runner.invoke(app, arguments)

    assert first.output.startswith("Revision 1 (new)")
    assert second.output.startswith("Revision 1 (unchanged)")


@pytest.mark.usefixtures("data_dir")
def test_status_rejects_option_like_refs(git_repo: GitFixture) -> None:
    git_repo.commit({"a.txt": "a\n"})

    result = runner.invoke(app, ["status", "--repo", str(git_repo.root), "--base", "main", "--", "--output=/tmp/x"])

    assert result.exit_code == 2
    assert "Not a valid commit reference" in result.output


@pytest.mark.usefixtures("data_dir")
def test_bussola_toml_file_level_and_ignore_globs(git_repo: GitFixture) -> None:
    git_repo.commit({".bussola.toml": 'file_level = ["generated/*.py"]\nignore = ["docs/**"]\n', "a.txt": "a\n"})
    git_repo.branch("feature")
    git_repo.commit({"generated/models.py": "def f():\n    pass\n", "docs/guide.md": "hi\n", "app.py": "def g():\n    pass\n"})

    result = runner.invoke(app, ["status", "feature", "--base", "main", "--repo", str(git_repo.root)])

    assert sorted(result.output.splitlines()) == sorted(["new             function app.py::g", "new             file     generated/models.py"])
