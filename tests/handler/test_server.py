import ipaddress
import socket
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI

from bussola.errors import InvalidRequestError
from bussola.handler.server import (
    Launcher,
    PublishedServer,
    ServerAddress,
    ServerStartError,
    is_healthy,
    publish_server,
    published_servers,
    start_server,
    withdraw_server,
)

TOKEN = "secret-token"


class FakeProcess:
    def __init__(self, exit_code: int | None) -> None:
        self.exit_code = exit_code

    def poll(self) -> int | None:
        return self.exit_code


class FakeServers:
    def __init__(self, healthy: set[ServerAddress] | None = None, comes_up: bool = True, exit_code: int | None = None) -> None:
        self.healthy = healthy or set()
        self.comes_up = comes_up
        self.exit_code = exit_code
        self.started: list[ServerAddress] = []
        self.opened: list[str] = []

    def start(self, address: ServerAddress) -> FakeProcess:
        self.started.append(address)
        if self.comes_up:
            self.healthy.add(address)
        return FakeProcess(self.exit_code)

    def is_healthy(self, address: ServerAddress) -> bool:
        return address in self.healthy

    def launcher(self, data_dir: Path) -> Launcher:
        return Launcher(data_dir, start=self.start, healthy=self.is_healthy, open_browser=self.opened.append, sleep=lambda _seconds: None, timeout=0)


def test_address_url_carries_the_token_after_the_link_query() -> None:
    address = ServerAddress("127.0.0.1", 8765, TOKEN)

    assert address.url("/") == f"http://127.0.0.1:8765/?token={TOKEN}"
    assert address.url("/github.com/a/b/pull/1?line=4") == f"http://127.0.0.1:8765/github.com/a/b/pull/1?line=4&token={TOKEN}"


def test_address_of_a_server_listening_everywhere_is_reached_on_localhost() -> None:
    assert ServerAddress(str(ipaddress.ip_address(0)), 9000, TOKEN).reachable() == ServerAddress("127.0.0.1", 9000, TOKEN)
    assert ServerAddress("::", 9000, TOKEN).reachable() == ServerAddress("127.0.0.1", 9000, TOKEN)
    assert ServerAddress("localhost", 9000, TOKEN).reachable() == ServerAddress("localhost", 9000, TOKEN)
    assert ServerAddress("::1", 9000, TOKEN).url("/") == f"http://[::1]:9000/?token={TOKEN}"


def test_published_server_is_private_and_withdrawn_only_by_its_owner(tmp_path: Path) -> None:
    address = ServerAddress("127.0.0.1", 8765, TOKEN)

    publish_server(tmp_path, address)
    withdraw_server(tmp_path, ServerAddress("127.0.0.1", 8765, "other"))

    assert published_servers(tmp_path) == [address]
    if sys.platform != "win32":
        assert stat.S_IMODE((tmp_path / "servers/8765.json").stat().st_mode) == 0o600
    withdraw_server(tmp_path, address)
    assert published_servers(tmp_path) == []


def test_servers_on_different_ports_are_all_published_default_port_first(tmp_path: Path) -> None:
    other = ServerAddress("127.0.0.1", 9000, "other")
    default = ServerAddress("127.0.0.1", 8765, TOKEN)
    publish_server(tmp_path, other)
    publish_server(tmp_path, default)

    assert published_servers(tmp_path) == [default, other]

    withdraw_server(tmp_path, other)
    assert published_servers(tmp_path) == [default]


def test_unreadable_server_files_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "servers").mkdir()
    (tmp_path / "servers/8765.json").write_text('{"host": "127.0.0.1"}')

    assert published_servers(tmp_path) == []


def test_open_uses_the_running_server(tmp_path: Path) -> None:
    running = ServerAddress("127.0.0.1", 9000, TOKEN)
    publish_server(tmp_path, ServerAddress("127.0.0.1", 8765, "stale"))
    publish_server(tmp_path, running)
    servers = FakeServers({running})

    url = servers.launcher(tmp_path).open("bussola://review?repo=acme/widgets&pr=7&path=src/app.py&line=42")

    assert servers.started == []
    assert servers.opened == [url]
    assert url == f"http://127.0.0.1:9000/github.com/acme/widgets/pull/7?path=src%2Fapp.py&line=42&token={TOKEN}"


def test_open_starts_the_server_when_it_is_not_running(tmp_path: Path) -> None:
    publish_server(tmp_path, ServerAddress("127.0.0.1", 9000, "stale"))
    servers = FakeServers()

    url = servers.launcher(tmp_path).open("bussola://")

    [started] = servers.started
    assert (started.host, started.port) == ("127.0.0.1", 8765)
    assert servers.opened == [f"http://127.0.0.1:8765/?token={started.token}"] == [url]


def test_open_finds_a_server_published_while_it_waits(tmp_path: Path) -> None:
    other = ServerAddress("127.0.0.1", 9000, TOKEN)
    servers = FakeServers(comes_up=False)

    def start(address: ServerAddress) -> FakeProcess:
        publish_server(tmp_path, other)
        servers.healthy.add(other)
        return servers.start(address)

    launcher = Launcher(tmp_path, start=start, healthy=servers.is_healthy, open_browser=servers.opened.append, sleep=lambda _seconds: None, timeout=0)

    assert launcher.open("bussola://") == f"http://127.0.0.1:9000/?token={TOKEN}"


def test_open_still_finds_a_server_that_another_link_started_when_its_own_exits(tmp_path: Path) -> None:
    winner = ServerAddress("127.0.0.1", 8765, "winner")
    servers = FakeServers(comes_up=False, exit_code=1)

    def winner_comes_up(_seconds: float) -> None:
        publish_server(tmp_path, winner)
        servers.healthy.add(winner)

    launcher = Launcher(tmp_path, start=servers.start, healthy=servers.is_healthy, open_browser=servers.opened.append, sleep=winner_comes_up, timeout=60)

    assert launcher.open("bussola://") == "http://127.0.0.1:8765/?token=winner"


def test_open_reports_a_server_that_does_not_come_up(tmp_path: Path) -> None:
    servers = FakeServers(comes_up=False)

    with pytest.raises(ServerStartError):
        servers.launcher(tmp_path).open("bussola://")

    assert servers.opened == []


def test_open_stops_waiting_as_soon_as_the_started_server_exits(tmp_path: Path) -> None:
    servers = FakeServers(comes_up=False, exit_code=1)
    naps: list[float] = []
    launcher = Launcher(
        tmp_path, start=servers.start, healthy=servers.is_healthy, open_browser=servers.opened.append, sleep=naps.append, timeout=60, exit_grace=0
    )

    with pytest.raises(ServerStartError, match="Another program may be using that port"):
        launcher.open("bussola://")

    assert naps == []


def test_invalid_links_neither_start_the_server_nor_open_the_browser(tmp_path: Path) -> None:
    servers = FakeServers()

    with pytest.raises(InvalidRequestError):
        servers.launcher(tmp_path).open("bussola://review?repo=acme/widgets&pr=7&approve=1&pr=8")

    assert servers.started == []
    assert servers.opened == []


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_published_server_announces_itself_only_while_it_listens(tmp_path: Path) -> None:
    address = ServerAddress("127.0.0.1", free_port(), TOKEN)
    instance = PublishedServer(uvicorn.Config(FastAPI(), host=address.host, port=address.port, log_level="warning"), tmp_path, address)
    thread = threading.Thread(target=instance.run)
    thread.start()
    deadline = time.monotonic() + 10
    while not published_servers(tmp_path) and time.monotonic() < deadline:
        time.sleep(0.05)

    assert instance.started
    assert published_servers(tmp_path) == [address]

    instance.should_exit = True
    thread.join(10)
    assert published_servers(tmp_path) == []


def test_a_server_that_cannot_listen_leaves_the_published_one_alone(tmp_path: Path) -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        running = ServerAddress("127.0.0.1", taken.getsockname()[1], "running")
        publish_server(tmp_path, running)
        address = ServerAddress("127.0.0.1", running.port, TOKEN)
        instance = PublishedServer(uvicorn.Config(FastAPI(), host=address.host, port=address.port, log_level="critical"), tmp_path, address)

        with pytest.raises(SystemExit):
            instance.run()

    assert published_servers(tmp_path) == [running]


def test_start_server_runs_serve_detached_with_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def popen(command: list[str], **options: Any) -> None:
        calls.append((command, options))

    monkeypatch.setattr("subprocess.Popen", popen)

    start_server(ServerAddress("127.0.0.1", 8765, TOKEN))

    [(command, options)] = calls
    assert command == [sys.executable, "-m", "bussola", "serve", "--no-open", "--no-register", "--host", "127.0.0.1", "--port", "8765"]
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


def test_health_check_of_a_port_that_does_not_speak_http_fails() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()

        def answer_garbage() -> None:
            connection, _ = listener.accept()
            with connection:
                connection.recv(1024)
                connection.sendall(b"not http\r\n\r\n")

        thread = threading.Thread(target=answer_garbage)
        thread.start()
        healthy = is_healthy(ServerAddress("127.0.0.1", listener.getsockname()[1], TOKEN))
        thread.join(5)

    assert not healthy


def test_health_check_of_a_closed_port_fails() -> None:
    with ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as unused:
        port = unused.server_address[1]

    assert not is_healthy(ServerAddress("127.0.0.1", port, TOKEN))
