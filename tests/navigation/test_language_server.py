from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from bussola.navigation import lsp
from bussola.navigation.lsp import LanguageServerError, LanguageServerSession, ServerLocation
from bussola.navigation.servers import LanguageServers, server_command
from bussola.navigation.specs import SERVER_SPECS
from tests.gitrepo import GitFixture
from tests.navigation.conftest import LanguageServerPath
from tests.navigation.test_index import ManualStarter

PYTHON = SERVER_SPECS["python"]
SOURCE = {"app/main.py": "from app.lib import helper\n\nhelper()\n", "app/lib.py": "def helper():\n    pass\n"}


def run_now(task: Callable[[], None]) -> None:
    task()


def definitions(position: ServerLocation) -> Callable[[LanguageServerSession], list[ServerLocation]]:
    return lambda session: session.definitions(position.path, position.row, position.character)


def references(position: ServerLocation) -> Callable[[LanguageServerSession], list[ServerLocation]]:
    return lambda session: session.references(position.path, position.row, position.character)


@pytest.fixture
def pool(tmp_path: Path) -> Iterator[LanguageServers]:
    servers = LanguageServers(tmp_path / "data" / "checkouts", run_now)
    yield servers
    servers.close()


def test_servers_are_detected_on_path_in_order_of_preference(servers: LanguageServerPath) -> None:
    assert server_command(PYTHON) is None

    servers.install("pyright-langserver")
    assert server_command(PYTHON) == [str(servers.bin_dir / "pyright-langserver"), "--stdio"]

    servers.install("basedpyright-langserver")
    assert server_command(PYTHON) == [str(servers.bin_dir / "basedpyright-langserver"), "--stdio"]


def test_definitions_come_from_a_checkout_of_the_commit(servers: LanguageServerPath, pool: LanguageServers, git_repo: GitFixture) -> None:
    servers.install("pyright-langserver", definition=[{"path": "app/lib.py", "line": 0, "character": 4}])
    commit = git_repo.commit(SOURCE)
    git_repo.write({"app/lib.py": "changed in the working tree\n"})

    found = pool.locate(git_repo.repo, commit, PYTHON, definitions(ServerLocation("app/main.py", 2, 0)))

    assert found == [ServerLocation("app/lib.py", 0, 4)]
    checkout = pool.checkout(commit)
    assert (checkout / "app" / "lib.py").read_text() == SOURCE["app/lib.py"]
    opened = [message["params"]["textDocument"] for message in servers.messages() if message.get("method") == "textDocument/didOpen"]
    assert opened == [{"uri": (checkout / "app/main.py").as_uri(), "languageId": "python", "version": 1, "text": SOURCE["app/main.py"]}]
    assert {"id": 900, "jsonrpc": "2.0", "result": [None]} in servers.messages()


def test_references_exclude_the_declaration_and_drop_files_outside_the_checkout(
    servers: LanguageServerPath, pool: LanguageServers, git_repo: GitFixture
) -> None:
    servers.install("pyright-langserver", references=[{"path": "app/main.py", "line": 2, "character": 0}, {"path": "../outside.py", "line": 0, "character": 0}])
    commit = git_repo.commit(SOURCE)

    found = pool.locate(git_repo.repo, commit, PYTHON, references(ServerLocation("app/lib.py", 0, 4)))

    assert found == [ServerLocation("app/main.py", 2, 0)]
    request = next(message for message in servers.messages() if message.get("method") == "textDocument/references")
    assert request["params"]["context"] == {"includeDeclaration": False}


def test_a_server_that_does_not_answer_in_time_gives_no_result(
    servers: LanguageServerPath, pool: LanguageServers, git_repo: GitFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lsp, "REQUEST_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(lsp, "SHUTDOWN_TIMEOUT_SECONDS", 0.2)
    servers.install("pyright-langserver", mode="hang", definition=[{"path": "app/lib.py", "line": 0, "character": 4}])
    commit = git_repo.commit(SOURCE)

    assert pool.locate(git_repo.repo, commit, PYTHON, definitions(ServerLocation("app/main.py", 2, 0))) == []


def test_a_server_that_crashes_gives_no_result_and_is_not_restarted(servers: LanguageServerPath, pool: LanguageServers, git_repo: GitFixture) -> None:
    servers.install("pyright-langserver", mode="crash")
    commit = git_repo.commit(SOURCE)

    assert pool.locate(git_repo.repo, commit, PYTHON, definitions(ServerLocation("app/main.py", 2, 0))) == []
    assert pool.locate(git_repo.repo, commit, PYTHON, definitions(ServerLocation("app/main.py", 2, 0))) == []
    assert servers.methods().count("initialize") == 1


def test_no_server_on_path_gives_no_result(pool: LanguageServers, git_repo: GitFixture) -> None:
    commit = git_repo.commit(SOURCE)

    assert pool.locate(git_repo.repo, commit, PYTHON, definitions(ServerLocation("app/main.py", 2, 0))) == []
    assert not pool.checkout(commit).exists()


def test_closing_shuts_servers_down_and_removes_checkouts(servers: LanguageServerPath, pool: LanguageServers, git_repo: GitFixture) -> None:
    servers.install("pyright-langserver", definition=[{"path": "app/lib.py", "line": 0, "character": 4}])
    commit = git_repo.commit(SOURCE)
    pool.locate(git_repo.repo, commit, PYTHON, definitions(ServerLocation("app/main.py", 2, 0)))

    pool.close()

    assert servers.methods()[-2:] == ["shutdown", "exit"]
    assert not pool.checkout(commit).exists()


def test_starting_a_missing_executable_raises(tmp_path: Path) -> None:
    with pytest.raises(LanguageServerError):
        LanguageServerSession.open([str(tmp_path / "missing")], tmp_path, PYTHON)


def test_servers_start_without_network_downloads(servers: LanguageServerPath, pool: LanguageServers, git_repo: GitFixture) -> None:
    servers.install("gopls", definition=[{"path": "main.go", "line": 0, "character": 5}])
    commit = git_repo.commit({"main.go": "package main\n\nfunc main() {}\n"})
    go = SERVER_SPECS["go"]

    assert pool.locate(git_repo.repo, commit, go, definitions(ServerLocation("main.go", 2, 5))) == [ServerLocation("main.go", 0, 5)]
    initialize = next(message for message in servers.messages() if message.get("method") == "initialize")
    assert servers.environment()["GOPROXY"] == "off"
    assert initialize["params"]["initializationOptions"] == {}
    assert SERVER_SPECS["ecmascript"].initialization_options == {"disableAutomaticTypingAcquisition": True}


def test_a_checkout_skips_links_that_point_outside_it(servers: LanguageServerPath, pool: LanguageServers, git_repo: GitFixture) -> None:
    servers.install("pyright-langserver", definition=[{"path": "app/lib.py", "line": 0, "character": 4}])
    git_repo.write(SOURCE)
    (git_repo.root / "absolute").symlink_to("/etc/hosts")
    (git_repo.root / "outside").symlink_to("../../elsewhere")
    (git_repo.root / "inside").symlink_to("app/lib.py")
    git_repo.git("add", "-A")
    git_repo.git("commit", "-q", "-m", "links")
    commit = git_repo.git("rev-parse", "HEAD")

    found = pool.locate(git_repo.repo, commit, PYTHON, definitions(ServerLocation("app/main.py", 2, 0)))

    checkout = pool.checkout(commit)
    assert found == [ServerLocation("app/lib.py", 0, 4)]
    assert sorted(path.name for path in checkout.iterdir()) == ["app", "inside"]


def test_a_server_still_starting_when_the_pool_closes_is_not_left_running(servers: LanguageServerPath, git_repo: GitFixture, tmp_path: Path) -> None:
    servers.install("pyright-langserver", definition=[{"path": "app/lib.py", "line": 0, "character": 4}])
    commit = git_repo.commit(SOURCE)
    starter = ManualStarter()
    pool = LanguageServers(tmp_path / "data" / "checkouts", starter)

    assert pool.locate(git_repo.repo, commit, PYTHON, definitions(ServerLocation("app/main.py", 2, 0))) == []
    pool.close()
    starter.run()

    assert servers.methods() == []
    assert not pool.checkout(commit).exists()
    assert pool.locate(git_repo.repo, commit, PYTHON, definitions(ServerLocation("app/main.py", 2, 0))) == []
    assert starter.tasks == []


def test_locations_with_percent_signs_in_their_path_are_kept(servers: LanguageServerPath, pool: LanguageServers, git_repo: GitFixture) -> None:
    servers.install("pyright-langserver", definition=[{"path": "app/rate%2541.py", "line": 0, "character": 4}])
    commit = git_repo.commit({**SOURCE, "app/rate%41.py": "def helper():\n    pass\n"})

    found = pool.locate(git_repo.repo, commit, PYTHON, definitions(ServerLocation("app/main.py", 2, 0)))

    assert found == [ServerLocation("app/rate%41.py", 0, 4)]
