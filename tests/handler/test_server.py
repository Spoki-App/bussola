import ipaddress
import json
import socket
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Generator, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI

from bussola.errors import InvalidRequestError
from bussola.handler.server import (
    Launcher,
    Probe,
    PublishedServer,
    ServerAddress,
    ServerStartError,
    port_is_free,
    probe_server,
    publish_server,
    published_servers,
    start_server,
    withdraw_server,
)
from bussola.security import INVALID_TOKEN_CODE

TOKEN = "secret-token"


class FakeProcess:
    def __init__(self, exit_code: int | None) -> None:
        self.exit_code = exit_code

    def poll(self) -> int | None:
        return self.exit_code


class FakeServers:
    def __init__(self, healthy: set[ServerAddress] | None = None, comes_up: bool = True, exit_code: int | None = None, taken_port: int | None = None) -> None:
        self.healthy = healthy or set()
        self.comes_up = comes_up
        self.exit_code = exit_code
        self.taken_port = taken_port
        self.started: list[ServerAddress] = []
        self.opened: list[str] = []
        self.busy: dict[ServerAddress, int] = {}

    def start(self, address: ServerAddress, _environment: Mapping[str, str]) -> FakeProcess:
        self.started.append(address)
        if address.port == self.taken_port:
            return FakeProcess(1)
        if self.comes_up:
            self.healthy.add(address)
        return FakeProcess(self.exit_code)

    def open_browser(self, url: str) -> bool:
        self.opened.append(url)
        return True

    def probe(self, address: ServerAddress) -> Probe:
        if self.busy.get(address, 0) > 0:
            self.busy[address] -= 1
            return Probe.SILENT
        if address in self.healthy:
            return Probe.READY
        listening = {(running.host, running.port) for running in self.healthy}
        return Probe.OTHER_BUSSOLA if (address.host, address.port) in listening else Probe.CLOSED

    def port_free(self, host: str, port: int) -> bool:
        return port != self.taken_port and all((running.host, running.port) != (host, port) for running in self.healthy)

    def launcher(self, data_dir: Path, *, sleep: Callable[[float], object] = lambda _seconds: None, timeout: float = 0, exit_grace: float = 0) -> Launcher:
        return Launcher(
            data_dir,
            start=self.start,
            probe=self.probe,
            open_browser=self.open_browser,
            sleep=sleep,
            timeout=timeout,
            exit_grace=exit_grace,
            port_free=self.port_free,
        )


def test_address_url_carries_the_token_after_the_link_query() -> None:
    address = ServerAddress("127.0.0.1", 8765, TOKEN)

    assert address.url("/") == f"http://127.0.0.1:8765/?token={TOKEN}"
    assert address.url("/github.com/a/b/pull/1?line=4") == f"http://127.0.0.1:8765/github.com/a/b/pull/1?line=4&token={TOKEN}"


def test_address_of_a_server_listening_everywhere_is_reached_on_localhost() -> None:
    assert ServerAddress(str(ipaddress.ip_address(0)), 9000, TOKEN).reachable() == ServerAddress("127.0.0.1", 9000, TOKEN)
    assert ServerAddress("::", 9000, TOKEN).reachable() == ServerAddress("::1", 9000, TOKEN)
    assert ServerAddress("localhost", 9000, TOKEN).reachable() == ServerAddress("localhost", 9000, TOKEN)
    assert ServerAddress("::1", 9000, TOKEN).url("/") == f"http://[::1]:9000/?token={TOKEN}"


def test_published_server_is_private_and_withdrawn_only_by_its_owner(tmp_path: Path) -> None:
    address = ServerAddress("127.0.0.1", 8765, TOKEN)

    publish_server(tmp_path, address)
    withdraw_server(tmp_path, ServerAddress("127.0.0.1", 8765, "other"))

    assert published_servers(tmp_path) == [address]
    if sys.platform != "win32":
        assert stat.S_IMODE((tmp_path / "servers/127.0.0.1-8765.json").stat().st_mode) == 0o600
    withdraw_server(tmp_path, address)
    assert published_servers(tmp_path) == []


def test_withdrawing_keeps_another_servers_file_without_hard_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    running = ServerAddress("127.0.0.1", 8765, "running")
    publish_server(tmp_path, running)

    def no_hard_links(_source: object, _target: object) -> None:
        raise PermissionError("hard links are not supported here")

    monkeypatch.setattr("os.link", no_hard_links)
    withdraw_server(tmp_path, ServerAddress("127.0.0.1", 8765, "gone"))

    assert published_servers(tmp_path) == [running]
    assert [path.name for path in (tmp_path / "servers").iterdir()] == ["127.0.0.1-8765.json"]


def test_servers_on_different_ports_are_all_published_default_port_first(tmp_path: Path) -> None:
    other = ServerAddress("127.0.0.1", 9000, "other")
    default = ServerAddress("127.0.0.1", 8765, TOKEN)
    publish_server(tmp_path, other)
    publish_server(tmp_path, default)

    assert published_servers(tmp_path) == [default, other]

    withdraw_server(tmp_path, other)
    assert published_servers(tmp_path) == [default]


def test_servers_on_the_same_port_but_other_hosts_keep_their_own_files(tmp_path: Path) -> None:
    local = ServerAddress("127.0.0.1", 8765, TOKEN)
    lan = ServerAddress("192.168.1.5", 8765, "lan")
    ipv6 = ServerAddress("::1", 8765, "ipv6")
    for address in (local, lan, ipv6):
        publish_server(tmp_path, address)

    withdraw_server(tmp_path, lan)

    assert sorted(published_servers(tmp_path), key=lambda address: address.host) == [local, ipv6]
    assert sorted(path.name for path in (tmp_path / "servers").iterdir()) == ["127.0.0.1-8765.json", "__1-8765.json"]


def test_unreadable_server_files_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "servers").mkdir()
    (tmp_path / "servers/127.0.0.1-8765.json").write_text('{"host": "127.0.0.1"}')

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

    def start(address: ServerAddress, environment: Mapping[str, str]) -> FakeProcess:
        publish_server(tmp_path, other)
        servers.healthy.add(other)
        return servers.start(address, environment)

    launcher = Launcher(tmp_path, start=start, probe=servers.probe, open_browser=servers.open_browser, sleep=lambda _seconds: None, timeout=0)

    assert launcher.open("bussola://") == f"http://127.0.0.1:9000/?token={TOKEN}"


def test_open_finds_the_server_another_link_started_once_it_publishes(tmp_path: Path) -> None:
    winner = ServerAddress("127.0.0.1", 8765, "winner")
    servers = FakeServers({winner}, comes_up=False, exit_code=1)
    naps: list[float] = []

    def winner_publishes_late(seconds: float) -> None:
        naps.append(seconds)
        if len(naps) == 3:
            publish_server(tmp_path, winner)

    launcher = servers.launcher(tmp_path, sleep=winner_publishes_late, timeout=60, exit_grace=60)

    assert launcher.open("bussola://") == "http://127.0.0.1:8765/?token=winner"
    assert len(naps) == 3


def test_open_tries_another_free_port_if_the_first_one_is_taken_meanwhile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ports = iter([20001, 20002])

    def next_port(_host: str) -> int:
        return next(ports)

    monkeypatch.setattr("bussola.handler.server.free_port", next_port)
    servers = FakeServers(taken_port=8765)

    def start(address: ServerAddress, environment: Mapping[str, str]) -> FakeProcess:
        if address.port == 20001:
            servers.started.append(address)
            return FakeProcess(1)
        return servers.start(address, environment)

    launcher = Launcher(
        tmp_path, start=start, probe=servers.probe, open_browser=servers.open_browser, sleep=lambda _seconds: None, timeout=60, port_free=servers.port_free
    )

    assert launcher.open("bussola://").startswith("http://127.0.0.1:20002/")
    assert [address.port for address in servers.started] == [20001, 20002]


def test_port_is_free_ignores_connections_left_in_time_wait() -> None:
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        client = socket.create_connection(("127.0.0.1", port))
        accepted, _ = listener.accept()
        accepted.close()
        client.close()

    if sys.platform != "win32":
        assert port_is_free("127.0.0.1", port)


def test_port_is_free_sees_a_server_listening_on_every_interface() -> None:
    with socket.socket() as everywhere:
        everywhere.bind((str(ipaddress.ip_address(0)), 0))
        everywhere.listen()

        assert not port_is_free("127.0.0.1", everywhere.getsockname()[1])


def test_probe_counts_a_connection_that_never_opens_as_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def time_out(_connection: object) -> None:
        raise TimeoutError

    monkeypatch.setattr("http.client.HTTPConnection.connect", time_out)

    assert probe_server(ServerAddress("127.0.0.1", 8765, TOKEN)) == Probe.CLOSED


def test_port_is_free_tells_a_taken_port_apart() -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]

        assert not port_is_free("127.0.0.1", port)

    assert port_is_free("127.0.0.1", port)


def test_open_starts_on_a_free_port_at_once_when_another_program_holds_8765(tmp_path: Path) -> None:
    servers = FakeServers(taken_port=8765)
    naps: list[float] = []

    url = servers.launcher(tmp_path, sleep=naps.append, timeout=60, exit_grace=60).open("bussola://")

    assert naps == []

    [started] = servers.started
    assert started.port != 8765
    assert url == f"http://127.0.0.1:{started.port}/?token={started.token}"


def test_open_does_not_start_a_second_server_while_the_first_is_still_starting(tmp_path: Path) -> None:
    servers = FakeServers(comes_up=False)

    with pytest.raises(ServerStartError, match="still starting"):
        servers.launcher(tmp_path).open("bussola://")

    assert len(servers.started) == 1


def test_open_waits_for_a_local_server_that_is_busy_instead_of_starting_another(tmp_path: Path) -> None:
    running = ServerAddress("127.0.0.1", 8765, TOKEN)
    publish_server(tmp_path, running)
    servers = FakeServers({running})
    servers.busy[running] = 3

    url = servers.launcher(tmp_path, timeout=60).open("bussola://")

    assert url == f"http://127.0.0.1:8765/?token={TOKEN}"
    assert servers.started == []


def test_open_waits_only_a_short_grace_for_a_silent_server(tmp_path: Path) -> None:
    hung = ServerAddress("127.0.0.1", 9000, "hung")
    publish_server(tmp_path, hung)
    servers = FakeServers()
    servers.busy[hung] = 10**6
    launcher = Launcher(
        tmp_path,
        start=servers.start,
        probe=servers.probe,
        open_browser=servers.open_browser,
        sleep=lambda _seconds: None,
        timeout=60,
        silent_grace=0,
        port_free=servers.port_free,
    )

    url = launcher.open("bussola://")

    [started] = servers.started
    assert url == f"http://127.0.0.1:8765/?token={started.token}"


def test_open_forgets_a_silent_server_as_soon_as_it_turns_out_closed(tmp_path: Path) -> None:
    gone = ServerAddress("127.0.0.1", 9000, "gone")
    publish_server(tmp_path, gone)
    servers = FakeServers()
    servers.busy[gone] = 1

    servers.launcher(tmp_path, timeout=60).open("bussola://")

    assert gone not in published_servers(tmp_path)


def test_open_gives_up_on_a_local_server_that_never_answers_and_starts_its_own(tmp_path: Path) -> None:
    hung = ServerAddress("127.0.0.1", 8765, "hung")
    publish_server(tmp_path, hung)
    servers = FakeServers(taken_port=8765)
    servers.busy[hung] = 10**6

    url = servers.launcher(tmp_path, timeout=0).open("bussola://")

    [started] = servers.started
    assert started.port != 8765
    assert url == f"http://127.0.0.1:{started.port}/?token={started.token}"
    assert hung in published_servers(tmp_path)

    servers.busy[hung] = 0
    servers.healthy.add(hung)
    publish_server(tmp_path, started)

    assert servers.launcher(tmp_path, timeout=0).open("bussola://") == "http://127.0.0.1:8765/?token=hung"


def test_open_probes_again_a_new_server_that_was_slow_to_answer_once(tmp_path: Path) -> None:
    winner = ServerAddress("127.0.0.1", 8765, "winner")
    servers = FakeServers({winner})

    def winner_publishes(_seconds: float) -> None:
        if winner not in published_servers(tmp_path):
            publish_server(tmp_path, winner)
            servers.busy[winner] = 1

    url = servers.launcher(tmp_path, sleep=winner_publishes, timeout=60, exit_grace=60).open("bussola://")

    assert url == "http://127.0.0.1:8765/?token=winner"
    assert servers.started == []


def test_open_forgets_a_server_file_whose_port_another_bussola_now_holds(tmp_path: Path) -> None:
    dead = ServerAddress("127.0.0.1", 9000, "dead")
    publish_server(tmp_path, dead)
    servers = FakeServers({ServerAddress("127.0.0.1", 9000, "someone else")})

    servers.launcher(tmp_path).open("bussola://")

    assert dead not in published_servers(tmp_path)


def test_open_forgets_a_server_file_whose_port_now_answers_as_something_else(tmp_path: Path) -> None:
    stale = ServerAddress("127.0.0.1", 9000, "stale")
    publish_server(tmp_path, stale)
    servers = FakeServers()

    def probe(address: ServerAddress) -> Probe:
        return Probe.WRONG if address == stale else servers.probe(address)

    launcher = Launcher(tmp_path, start=servers.start, probe=probe, open_browser=servers.open_browser, sleep=lambda _seconds: None, timeout=0)
    launcher.open("bussola://")

    assert stale not in published_servers(tmp_path)


def test_open_ignores_a_silent_server_on_another_host(tmp_path: Path) -> None:
    lan = ServerAddress("192.168.1.5", 8765, "lan")
    publish_server(tmp_path, lan)
    servers = FakeServers()
    servers.busy[lan] = 10**6

    url = servers.launcher(tmp_path).open("bussola://")

    [started] = servers.started
    assert url == f"http://127.0.0.1:8765/?token={started.token}"


def test_open_reports_a_browser_that_cannot_be_opened(tmp_path: Path) -> None:
    running = ServerAddress("127.0.0.1", 8765, TOKEN)
    publish_server(tmp_path, running)
    launcher = Launcher(tmp_path, probe=FakeServers({running}).probe, open_browser=lambda _url: False)

    with pytest.raises(ServerStartError, match="no browser could be opened"):
        launcher.open("bussola://")


def test_open_works_when_a_stale_server_file_cannot_be_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    running = ServerAddress("127.0.0.1", 8765, TOKEN)
    publish_server(tmp_path, ServerAddress("127.0.0.1", 9000, "gone"))
    publish_server(tmp_path, running)

    def locked(_path: Path, missing_ok: bool = False) -> None:
        raise PermissionError(missing_ok)

    monkeypatch.setattr(Path, "unlink", locked)

    assert FakeServers({running}).launcher(tmp_path).open("bussola://") == f"http://127.0.0.1:8765/?token={TOKEN}"


def test_open_forgets_server_files_whose_port_is_closed(tmp_path: Path) -> None:
    gone = ServerAddress("127.0.0.1", 9000, "gone")
    publish_server(tmp_path, gone)
    servers = FakeServers()

    servers.launcher(tmp_path).open("bussola://")

    assert published_servers(tmp_path) == []


def test_open_reports_a_server_that_does_not_come_up(tmp_path: Path) -> None:
    servers = FakeServers(comes_up=False, exit_code=1)

    with pytest.raises(ServerStartError):
        servers.launcher(tmp_path).open("bussola://")

    assert servers.opened == []


def test_open_stops_waiting_as_soon_as_the_started_server_exits(tmp_path: Path) -> None:
    servers = FakeServers(comes_up=False, exit_code=1)
    naps: list[float] = []
    launcher = servers.launcher(tmp_path, sleep=naps.append, timeout=60)

    with pytest.raises(ServerStartError, match="bussola did not start"):
        launcher.open("bussola://")

    assert naps == []
    assert len(servers.started) == 4


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


def test_a_server_that_cannot_publish_still_serves(tmp_path: Path) -> None:
    (tmp_path / "servers").write_text("a file, not a folder")
    address = ServerAddress("127.0.0.1", free_port(), TOKEN)
    instance = PublishedServer(uvicorn.Config(FastAPI(), host=address.host, port=address.port, log_level="critical"), tmp_path, address)
    thread = threading.Thread(target=instance.run)
    thread.start()
    deadline = time.monotonic() + 10
    while not instance.started and time.monotonic() < deadline:
        time.sleep(0.05)

    assert instance.started

    instance.should_exit = True
    thread.join(10)
    assert not thread.is_alive()


def test_start_server_runs_serve_detached_with_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def popen(command: list[str], **options: Any) -> None:
        calls.append((command, options))

    monkeypatch.setattr("subprocess.Popen", popen)

    start_server(ServerAddress("127.0.0.1", 8765, TOKEN), {"BUSSOLA_DATA_DIR": "/data/bussola", "PATH": "/opt/bin"})

    [(command, options)] = calls
    assert command == [sys.executable, "-P", "-m", "bussola", "serve", "--no-open", "--no-register", "--host", "127.0.0.1", "--port", "8765"]
    assert options["env"]["BUSSOLA_TOKEN"] == TOKEN
    assert options["env"]["BUSSOLA_DATA_DIR"] == "/data/bussola"
    assert options["env"]["PATH"] == "/opt/bin"
    assert options["stdin"] == options["stdout"] == options["stderr"] == subprocess.DEVNULL


def test_launcher_passes_its_data_dir_and_search_path_to_the_server(tmp_path: Path) -> None:
    environments: list[Mapping[str, str]] = []
    servers = FakeServers()

    def start(address: ServerAddress, environment: Mapping[str, str]) -> FakeProcess:
        environments.append(environment)
        return servers.start(address, environment)

    Launcher(tmp_path, start=start, probe=servers.probe, open_browser=servers.open_browser, port_free=servers.port_free, search_path="/opt/bin").open(
        "bussola://"
    )

    assert environments == [{"BUSSOLA_DATA_DIR": str(tmp_path), "PATH": "/opt/bin"}]


def serve_http(answer: Callable[[BaseHTTPRequestHandler], None]) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            answer(self)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


def answer_like_bussola(request: BaseHTTPRequestHandler) -> None:
    port = request.headers.get("Host", "").rsplit(":", 1)[-1]
    ok = request.path == "/api/health" and request.headers.get("Cookie") == f"bussola_token_{port}={TOKEN}"
    body = b'{"status":"ok","app":"bussola"}' if ok else json.dumps({"detail": "Missing or invalid session token", "code": INVALID_TOKEN_CODE}).encode()
    request.send_response(200 if ok else 403)
    request.send_header("Content-Length", str(len(body)))
    request.end_headers()
    request.wfile.write(body)


def answer_forbidden(request: BaseHTTPRequestHandler) -> None:
    request.send_response(403)
    request.send_header("Content-Length", "9")
    request.end_headers()
    request.wfile.write(b"Forbidden")


@pytest.fixture
def health_server() -> Generator[ServerAddress]:
    httpd = serve_http(answer_like_bussola)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield ServerAddress("127.0.0.1", httpd.server_address[1], TOKEN)
    httpd.shutdown()
    httpd.server_close()


def test_probe_needs_the_server_token_to_call_it_ready(health_server: ServerAddress) -> None:
    assert probe_server(health_server) == Probe.READY
    assert probe_server(ServerAddress(health_server.host, health_server.port, "wrong")) == Probe.OTHER_BUSSOLA


def answer_ok_to_everything(request: BaseHTTPRequestHandler) -> None:
    request.send_response(200)
    request.send_header("Content-Length", "15")
    request.end_headers()
    request.wfile.write(b"<html>hi</html>")


def test_probe_does_not_take_any_200_for_bussola() -> None:
    httpd = serve_http(answer_ok_to_everything)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    state = probe_server(ServerAddress("127.0.0.1", httpd.server_address[1], TOKEN))

    httpd.shutdown()
    httpd.server_close()
    assert state == Probe.WRONG


def test_probe_does_not_take_any_403_for_bussola() -> None:
    httpd = serve_http(answer_forbidden)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    state = probe_server(ServerAddress("127.0.0.1", httpd.server_address[1], TOKEN))

    httpd.shutdown()
    httpd.server_close()
    assert state == Probe.WRONG


def test_probe_of_a_port_that_does_not_speak_http_is_wrong() -> None:
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
        state = probe_server(ServerAddress("127.0.0.1", listener.getsockname()[1], TOKEN))
        thread.join(5)

    assert state == Probe.WRONG


def test_probe_of_a_server_that_accepts_but_never_answers_is_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bussola.handler.server.HEALTH_TIMEOUT_SECONDS", 0.2)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()

        state = probe_server(ServerAddress("127.0.0.1", listener.getsockname()[1], TOKEN))

    assert state == Probe.SILENT


def test_probe_of_a_closed_port_says_so() -> None:
    with ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as unused:
        port = unused.server_address[1]

    assert probe_server(ServerAddress("127.0.0.1", port, TOKEN)) == Probe.CLOSED
