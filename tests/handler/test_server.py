import stat
import subprocess
import sys
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from bussola.errors import InvalidRequestError
from bussola.handler.server import Launcher, ServerAddress, ServerStartError, claim_server, is_healthy, published_server, start_server, withdraw_server

TOKEN = "secret-token"


class FakeServers:
    def __init__(self, healthy: set[ServerAddress] | None = None, comes_up: bool = True) -> None:
        self.healthy = healthy or set()
        self.comes_up = comes_up
        self.started: list[ServerAddress] = []
        self.opened: list[str] = []

    def start(self, address: ServerAddress) -> None:
        self.started.append(address)
        if self.comes_up:
            self.healthy.add(address)

    def is_healthy(self, address: ServerAddress) -> bool:
        return address in self.healthy

    def launcher(self, data_dir: Path) -> Launcher:
        return Launcher(data_dir, start=self.start, healthy=self.is_healthy, open_browser=self.opened.append, sleep=lambda _seconds: None, timeout=0)


def test_address_url_carries_the_token_after_the_link_query() -> None:
    address = ServerAddress("127.0.0.1", 8765, TOKEN)

    assert address.url("/") == f"http://127.0.0.1:8765/?token={TOKEN}"
    assert address.url("/github.com/a/b/pull/1?line=4") == f"http://127.0.0.1:8765/github.com/a/b/pull/1?line=4&token={TOKEN}"


def test_published_server_is_private_and_withdrawn_only_by_its_owner(tmp_path: Path) -> None:
    address = ServerAddress("127.0.0.1", 8765, TOKEN)

    assert claim_server(tmp_path, address, healthy=lambda _address: False)
    withdraw_server(tmp_path, ServerAddress("127.0.0.1", 8765, "other"))

    assert published_server(tmp_path) == address
    if sys.platform != "win32":
        assert stat.S_IMODE((tmp_path / "server.json").stat().st_mode) == 0o600
    withdraw_server(tmp_path, address)
    assert published_server(tmp_path) is None


def test_a_second_server_does_not_replace_a_healthy_one(tmp_path: Path) -> None:
    first = ServerAddress("127.0.0.1", 8765, TOKEN)
    second = ServerAddress("127.0.0.1", 8766, "other")
    claim_server(tmp_path, first)

    assert not claim_server(tmp_path, second, healthy=lambda address: address == first)
    assert published_server(tmp_path) == first
    assert claim_server(tmp_path, second, healthy=lambda _address: False)
    assert published_server(tmp_path) == second


def test_unreadable_server_file_counts_as_no_server(tmp_path: Path) -> None:
    (tmp_path / "server.json").write_text('{"host": "127.0.0.1"}')

    assert published_server(tmp_path) is None


def test_open_uses_the_running_server(tmp_path: Path) -> None:
    running = ServerAddress("127.0.0.1", 9000, TOKEN)
    claim_server(tmp_path, running, healthy=lambda _address: False)
    servers = FakeServers({running})

    url = servers.launcher(tmp_path).open("bussola://review?repo=acme/widgets&pr=7&path=src/app.py&line=42")

    assert servers.started == []
    assert servers.opened == [url]
    assert url == f"http://127.0.0.1:9000/github.com/acme/widgets/pull/7?path=src%2Fapp.py&line=42&token={TOKEN}"


def test_open_starts_the_server_when_it_is_not_running(tmp_path: Path) -> None:
    claim_server(tmp_path, ServerAddress("127.0.0.1", 9000, "stale"), healthy=lambda _address: False)
    servers = FakeServers()

    url = servers.launcher(tmp_path).open("bussola://")

    [started] = servers.started
    assert (started.host, started.port) == ("127.0.0.1", 8765)
    assert servers.opened == [f"http://127.0.0.1:8765/?token={started.token}"] == [url]


def test_open_reports_a_server_that_does_not_come_up(tmp_path: Path) -> None:
    servers = FakeServers(comes_up=False)

    with pytest.raises(ServerStartError):
        servers.launcher(tmp_path).open("bussola://")

    assert servers.opened == []


def test_invalid_links_neither_start_the_server_nor_open_the_browser(tmp_path: Path) -> None:
    servers = FakeServers()

    with pytest.raises(InvalidRequestError):
        servers.launcher(tmp_path).open("bussola://review?repo=acme/widgets&pr=7&approve=1&pr=8")

    assert servers.started == []
    assert servers.opened == []


def test_start_server_runs_serve_detached_with_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def popen(command: list[str], **options: Any) -> None:
        calls.append((command, options))

    monkeypatch.setattr("subprocess.Popen", popen)

    start_server(ServerAddress("127.0.0.1", 8765, TOKEN))

    [(command, options)] = calls
    assert command == [sys.executable, "-m", "bussola", "serve", "--no-open", "--host", "127.0.0.1", "--port", "8765"]
    assert options["env"]["BUSSOLA_TOKEN"] == TOKEN
    assert options["stdin"] == options["stdout"] == options["stderr"] == subprocess.DEVNULL


@pytest.fixture
def health_server() -> Generator[ServerAddress]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            ok = self.path == "/api/health" and self.headers.get("Cookie") == f"bussola_token={TOKEN}"
            self.send_response(200 if ok else 403)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield ServerAddress("127.0.0.1", httpd.server_address[1], TOKEN)
    httpd.shutdown()
    httpd.server_close()


def test_health_check_needs_the_server_token(health_server: ServerAddress) -> None:
    assert is_healthy(health_server)
    assert not is_healthy(ServerAddress(health_server.host, health_server.port, "wrong"))


def test_health_check_of_a_closed_port_fails() -> None:
    with ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as unused:
        port = unused.server_address[1]

    assert not is_healthy(ServerAddress("127.0.0.1", port, TOKEN))
