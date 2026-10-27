from typer.testing import CliRunner

from rtool.cli import app
from tests.gitrepo import GitFixture

runner = CliRunner()


def test_status_prints_units_in_scope(git_repo: GitFixture) -> None:
    git_repo.commit({"app.py": "def f():\n    return 1\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": "def f():\n    return 2\n"})

    result = runner.invoke(app, ["status", "feature", "--repo", str(git_repo.root)])

    assert result.exit_code == 0
    assert result.output.split() == ["modified", "function", "app.py::f"]


def test_status_uses_rtool_toml_base_branch(git_repo: GitFixture) -> None:
    git_repo.commit({".rtool.toml": 'base_branch = "trunk"\n', "a.txt": "a\n"})
    git_repo.branch("trunk")
    git_repo.branch("feature")
    git_repo.commit({"a.txt": "b\n"})

    result = runner.invoke(app, ["status", "feature", "--repo", str(git_repo.root)])

    assert result.exit_code == 0
    assert result.output.split() == ["modified", "file", "a.txt"]


def test_status_rejects_option_like_refs(git_repo: GitFixture) -> None:
    git_repo.commit({"a.txt": "a\n"})

    result = runner.invoke(app, ["status", "--repo", str(git_repo.root), "--base", "main", "--", "--output=/tmp/x"])

    assert result.exit_code == 2
    assert "Not a valid commit reference" in result.output
