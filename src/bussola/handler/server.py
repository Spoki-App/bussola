import asyncio
import http.client
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

SERVER_FILE = "server.json"
LINK_LOG_FILE = "open-link.log"
HEALTH_PATH = "/api/health"
HEALTH_TIMEOUT_SECONDS = 2.0
START_TIMEOUT_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 0.25


class ServerStartError(DomainError):
    pass


@dataclass(frozen=True)
class ServerAddress:
    host: str
    port: int
    token: str

    def url(self, path: str) -> str:
        separator = "&" if "?" in path else "?"
        return f"http://{self.host}:{self.port}{path}{separator}{urlencode({TOKEN_QUERY: self.token})}"


SERVER_ADDRESS = TypeAdapter(ServerAddress)


def server_file(data_dir: Path) -> Path:
    return data_dir / SERVER_FILE


def publish_server(data_dir: Path, address: ServerAddress) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=data_dir, prefix=".server-", suffix=".json")
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(SERVER_ADDRESS.dump_json(address).decode())
    Path(temporary).replace(server_file(data_dir))


def withdraw_server(data_dir: Path, address: ServerAddress) -> None:
    if published_server(data_dir) == address:
        server_file(data_dir).unlink(missing_ok=True)


def published_server(data_dir: Path) -> ServerAddress | None:
    try:
        return SERVER_ADDRESS.validate_json(server_file(data_dir).read_bytes())
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


def claim_server(data_dir: Path, address: ServerAddress, healthy: Callable[[ServerAddress], bool] = is_healthy) -> None:
    running = published_server(data_dir)
    if running is None or running == address or not healthy(running):
        publish_server(data_dir, address)


def record_link_error(data_dir: Path, link: str, error: Exception) -> None:
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
        await asyncio.to_thread(claim_server, self.data_dir, self.address)

    async def shutdown(self, sockets: list[socket.socket] | None = None) -> None:
        withdraw_server(self.data_dir, self.address)
        await super().shutdown(sockets)


def run_published(app: Any, data_dir: Path, address: ServerAddress) -> None:
    PublishedServer(uvicorn.Config(app, host=address.host, port=address.port, log_level="warning"), data_dir, address).run()


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

    def open(self, link: str) -> str:
        path = browser_path(parse_link(link))
        url = self.ensure_server().url(path)
        self.open_browser(url)
        return url

    def ensure_server(self) -> ServerAddress:
        running = published_server(self.data_dir)
        if running is not None and self.healthy(running):
            return running
        address = ServerAddress(DEFAULT_HOST, DEFAULT_PORT, new_token())
        found = self._wait_for_server(address, self.start(address))
        if found is None:
            raise ServerStartError(
                f"bussola did not start on {address.host}:{address.port}. Another program may be using that port. Run `bussola serve` to see why."
            )
        return found

    def _wait_for_server(self, started: ServerAddress, process: Process) -> ServerAddress | None:
        deadline = time.monotonic() + self.timeout
        while True:
            published = published_server(self.data_dir)
            candidates = [started] if published in (None, started) else [started, published]
            found = next((candidate for candidate in candidates if self.healthy(candidate)), None)
            if found is not None or process.poll() is not None or time.monotonic() >= deadline:
                return found
            self.sleep(POLL_INTERVAL_SECONDS)
