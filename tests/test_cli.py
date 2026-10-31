import os
from collections.abc import Sequence
from pathlib import Path

import pytest
from fastapi import FastAPI
from typer.testing import CliRunner

from bussola.cli import app
from bussola.handler import registration, server
from tests.apiclient import ApiClient
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


def test_install_and_uninstall_handler_apply_the_platform_registration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[tuple[str, ...]] = []
    handler = registration.linux_registration(("/usr/bin/python3", "-m", "bussola", "open-link"), tmp_path / "applications", tmp_path / "mimeapps.list")

    def record(argv: Sequence[str]) -> None:
        commands.append(tuple(argv))

    monkeypatch.setattr(registration, "current_registration", lambda: handler)
    monkeypatch.setattr(registration, "run_command", record)
    desktop = tmp_path / "applications" / "bussola-url-handler.desktop"

    installed = runner.invoke(app, ["install-handler"])

    assert installed.exit_code == 0, installed.output
    assert desktop.is_file()
    assert commands[1] == ("xdg-mime", "default", "bussola-url-handler.desktop", "x-scheme-handler/bussola")

    removed = runner.invoke(app, ["uninstall-handler"])

    assert removed.exit_code == 0, removed.output
    assert not desktop.exists()


def test_install_handler_reports_unsupported_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "aix")

    result = runner.invoke(app, ["install-handler"])

    assert result.exit_code == 2
    assert "not supported on aix" in result.output


def test_open_link_refuses_invalid_links_before_looking_for_the_server_and_logs_why(data_dir: Path) -> None:
    result = runner.invoke(app, ["open-link", "bussola://review?repo=acme/widgets"])

    assert result.exit_code == 2
    assert "pr parameter" in result.output
    assert not (data_dir / "servers").exists()
    log = (data_dir / "open-link.log").read_text()
    assert "'bussola://review?repo=acme/widgets': The pr parameter must be a positive number" in log


def test_open_link_logs_unexpected_failures_too(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_launcher: server.Launcher, _link: str) -> str:
        raise FileNotFoundError("python is gone")

    monkeypatch.setattr(server.Launcher, "open", fail)

    result = runner.invoke(app, ["open-link", "bussola://"])

    assert result.exit_code != 0
    assert "'bussola://': python is gone" in (data_dir / "open-link.log").read_text()


def test_serve_registers_the_folder_unless_told_not_to(git_repo: GitFixture, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git_repo.commit({"a.txt": "a\n"})
    published: list[server.ServerAddress] = []

    def run(_application: FastAPI, _data_dir: Path, address: server.ServerAddress) -> None:
        published.append(address)

    monkeypatch.setenv("BUSSOLA_TOKEN", "fixed-token")
    monkeypatch.setattr("bussola.cli.run_published", run)
    repos = ApiClient.create(git_repo, data_dir)

    skipped = runner.invoke(app, ["serve", "--no-open", "--no-register", "--port", "9123", "--repo", str(git_repo.root)])
    assert repos.call("GET", "/repos") == []
    assert "BUSSOLA_TOKEN" not in os.environ
    monkeypatch.setenv("BUSSOLA_TOKEN", "fixed-token")
    registered = runner.invoke(app, ["serve", "--no-open", "--port", "9123", "--repo", str(git_repo.root)])

    assert skipped.exit_code == registered.exit_code == 0, skipped.output + registered.output
    assert "http://127.0.0.1:9123/?token=fixed-token" in registered.output
    assert [repo["path"] for repo in repos.call("GET", "/repos")] == [str(git_repo.root)]
    assert published == [server.ServerAddress("127.0.0.1", 9123, "fixed-token")] * 2
