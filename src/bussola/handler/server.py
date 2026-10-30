import http.client
import os
import subprocess
import sys
import time
import webbrowser
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from pydantic import TypeAdapter, ValidationError

from bussola.config import DEFAULT_HOST, DEFAULT_PORT
from bussola.errors import DomainError
from bussola.handler.links import browser_path, parse_link
from bussola.security import TOKEN_COOKIE, TOKEN_ENV, TOKEN_QUERY, new_token

SERVER_FILE = "server.json"
HEALTH_PATH = "/api/health"
HEALTH_TIMEOUT_SECONDS = 2.0
START_TIMEOUT_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 0.25
PRIVATE_FILE_MODE = 0o600


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
    path = server_file(data_dir)
    path.unlink(missing_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, PRIVATE_FILE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(SERVER_ADDRESS.dump_json(address).decode())


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
    except OSError:
        return False
    finally:
        connection.close()


def claim_server(data_dir: Path, address: ServerAddress, healthy: Callable[[ServerAddress], bool] = is_healthy) -> bool:
    running = published_server(data_dir)
    if running is not None and running != address and healthy(running):
        return False
    publish_server(data_dir, address)
    return True


def published_while_running(data_dir: Path, address: ServerAddress) -> Callable[[object], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_app: object) -> AsyncGenerator[None]:
        claim_server(data_dir, address)
        try:
            yield
        finally:
            withdraw_server(data_dir, address)

    return lifespan


def start_server(address: ServerAddress) -> None:
    command = [sys.executable, "-m", "bussola", "serve", "--no-open", "--host", address.host, "--port", str(address.port)]
    subprocess.Popen(
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
    start: Callable[[ServerAddress], object] = start_server
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
        self.start(address)
        if not self._wait_until_healthy(address):
            raise ServerStartError(f"bussola did not start on {address.host}:{address.port}. Run `bussola serve` to see why.")
        return address

    def _wait_until_healthy(self, address: ServerAddress) -> bool:
        deadline = time.monotonic() + self.timeout
        while not self.healthy(address):
            if time.monotonic() >= deadline:
                return False
            self.sleep(POLL_INTERVAL_SECONDS)
        return True
