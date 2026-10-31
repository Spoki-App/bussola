import contextlib
import http.client
import ipaddress
import os
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

import uvicorn
from pydantic import TypeAdapter, ValidationError

from bussola.config import DEFAULT_HOST, DEFAULT_PORT
from bussola.errors import DomainError
from bussola.handler.links import browser_path, parse_link
from bussola.security import TOKEN_COOKIE, TOKEN_ENV, TOKEN_QUERY, new_token

SERVERS_DIR = "servers"
LINK_LOG_FILE = "open-link.log"
HEALTH_PATH = "/api/health"
HEALTH_TIMEOUT_SECONDS = 2.0
START_TIMEOUT_SECONDS = 30.0
EXIT_GRACE_SECONDS = 5.0
POLL_INTERVAL_SECONDS = 0.25


class ServerStartError(DomainError):
    pass


@dataclass(frozen=True)
class ServerAddress:
    host: str
    port: int
    token: str

    def url(self, path: str) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        separator = "&" if "?" in path else "?"
        return f"http://{host}:{self.port}{path}{separator}{urlencode({TOKEN_QUERY: self.token})}"

    def reachable(self) -> "ServerAddress":
        return ServerAddress(DEFAULT_HOST, self.port, self.token) if _listens_everywhere(self.host) else self


SERVER_ADDRESS = TypeAdapter(ServerAddress)


def _listens_everywhere(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_unspecified
    except ValueError:
        return not host


def server_file(data_dir: Path, port: int) -> Path:
    return data_dir / SERVERS_DIR / f"{port}.json"


def publish_server(data_dir: Path, address: ServerAddress) -> None:
    folder = data_dir / SERVERS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=folder, suffix=".tmp")
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(SERVER_ADDRESS.dump_json(address).decode())
    Path(temporary).replace(server_file(data_dir, address.port))


def withdraw_server(data_dir: Path, address: ServerAddress) -> None:
    path = server_file(data_dir, address.port)
    if _read_address(path) == address:
        path.unlink(missing_ok=True)


def published_servers(data_dir: Path) -> list[ServerAddress]:
    found = [address for path in (data_dir / SERVERS_DIR).glob("*.json") if (address := _read_address(path)) is not None]
    return sorted(found, key=lambda address: (address.port != DEFAULT_PORT, address.port))


def _read_address(path: Path) -> ServerAddress | None:
    try:
        return SERVER_ADDRESS.validate_json(path.read_bytes())
    except (OSError, ValidationError):
        return None


def is_healthy(address: ServerAddress) -> bool:
    connection = http.client.HTTPConnection(address.host, address.port, timeout=HEALTH_TIMEOUT_SECONDS)
    try:
        connection.request("GET", HEALTH_PATH, headers={"Cookie": f"{TOKEN_COOKIE}={address.token}"})
        return connection.getresponse().status == HTTPStatus.OK
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def record_link_error(data_dir: Path, link: str, error: Exception) -> None:
    with contextlib.suppress(OSError):
        data_dir.mkdir(parents=True, exist_ok=True)
        with (data_dir / LINK_LOG_FILE).open("a", encoding="utf-8") as file:
            file.write(f"{datetime.now(UTC).isoformat(timespec='seconds')} {link!r}: {error}\n")


class PublishedServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, data_dir: Path, address: ServerAddress) -> None:
        super().__init__(config)
        self.data_dir = data_dir
        self.address = address

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets)
        publish_server(self.data_dir, self.address)

    async def shutdown(self, sockets: list[socket.socket] | None = None) -> None:
        withdraw_server(self.data_dir, self.address)
        await super().shutdown(sockets)


def run_published(app: Any, data_dir: Path, address: ServerAddress) -> None:
    config = uvicorn.Config(app, host=address.host, port=address.port, log_level="warning")
    PublishedServer(config, data_dir, address.reachable()).run()


class Process(Protocol):
    def poll(self) -> int | None: ...


def start_server(address: ServerAddress) -> Process:
    command = [sys.executable, "-m", "bussola", "serve", "--no-open", "--no-register", "--host", address.host, "--port", str(address.port)]
    return subprocess.Popen(
        command,
        env={**os.environ, TOKEN_ENV: address.token},
        cwd=Path.home(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **_detached(),
    )


def _detached() -> dict[str, Any]:
    if sys.platform == "win32":
        return {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


@dataclass(frozen=True)
class Launcher:
    data_dir: Path
    start: Callable[[ServerAddress], Process] = start_server
    healthy: Callable[[ServerAddress], bool] = is_healthy
    open_browser: Callable[[str], object] = webbrowser.open
    sleep: Callable[[float], object] = time.sleep
    timeout: float = START_TIMEOUT_SECONDS
    exit_grace: float = EXIT_GRACE_SECONDS

    def open(self, link: str) -> str:
        path = browser_path(parse_link(link))
        url = self.ensure_server().url(path)
        self.open_browser(url)
        return url

    def ensure_server(self) -> ServerAddress:
        running = self._first_healthy()
        if running is not None:
            return running
        address = ServerAddress(DEFAULT_HOST, DEFAULT_PORT, new_token())
        found = self._wait_for_server(address, self.start(address))
        if found is None:
            raise ServerStartError(
                f"bussola did not start on {address.host}:{address.port}. Another program may be using that port. Run `bussola serve` to see why."
            )
        return found

    def _first_healthy(self, *extra: ServerAddress) -> ServerAddress | None:
        candidates = dict.fromkeys([*extra, *published_servers(self.data_dir)])
        return next((candidate for candidate in candidates if self.healthy(candidate)), None)

    def _wait_for_server(self, started: ServerAddress, process: Process) -> ServerAddress | None:
        deadline = time.monotonic() + self.timeout
        while True:
            found = self._first_healthy(started)
            if found is not None:
                return found
            if process.poll() is not None:
                deadline = min(deadline, time.monotonic() + self.exit_grace)
            if time.monotonic() >= deadline:
                return None
            self.sleep(POLL_INTERVAL_SECONDS)
