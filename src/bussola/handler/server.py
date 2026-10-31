import contextlib
import hashlib
import http.client
import ipaddress
import logging
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from collections.abc import Callable, Mapping, Set
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

import uvicorn
from pydantic import BaseModel, TypeAdapter, ValidationError

from bussola.config import DEFAULT_HOST, DEFAULT_PORT
from bussola.errors import DomainError
from bussola.handler.links import BUSSOLA_MODULE, browser_path, parse_link
from bussola.security import INVALID_TOKEN_CODE, TOKEN_ENV, TOKEN_QUERY, host_port, is_ipv6_host, is_local_host, new_token, token_cookie
from bussola.storage.database import APP_NAME, DATA_DIR_ENV

SERVERS_DIR = "servers"
LINK_LOG_FILE = "open-link.log"
HEALTH_PATH = "/api/health"
HEALTH_TIMEOUT_SECONDS = 2.0
START_TIMEOUT_SECONDS = 30.0
EXIT_GRACE_SECONDS = 1.0
SILENT_GRACE_SECONDS = 5.0
FREE_PORT_ATTEMPTS = 3
NOTHING_TO_SKIP: frozenset["ServerAddress"] = frozenset()
MAX_PROBE_BODY = 512
MAX_LINK_LOG_BYTES = 1_000_000
MAX_LOGGED_LINK = 500
IPV6_LOOPBACK = "::1"
TOKEN_FINGERPRINT_LENGTH = 16
UNSAFE_FILE_CHARACTERS = re.compile(r"[^A-Za-z0-9.-]")
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
        return f"http://{host_port(self.host, self.port)}{path}{separator}{urlencode({TOKEN_QUERY: self.token})}"

    def reachable(self) -> "ServerAddress":
        if not _listens_everywhere(self.host):
            return self
        return ServerAddress(IPV6_LOOPBACK if is_ipv6_host(self.host) else DEFAULT_HOST, self.port, self.token)


SERVER_ADDRESS = TypeAdapter(ServerAddress)
logger = logging.getLogger(__name__)


def _listens_everywhere(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_unspecified
    except ValueError:
        return not host


def server_file(data_dir: Path, address: ServerAddress) -> Path:
    fingerprint = hashlib.sha256(address.token.encode()).hexdigest()[:TOKEN_FINGERPRINT_LENGTH]
    return data_dir / SERVERS_DIR / f"{UNSAFE_FILE_CHARACTERS.sub('_', address.host)}-{address.port}-{fingerprint}.json"


def publish_server(data_dir: Path, address: ServerAddress) -> None:
    folder = data_dir / SERVERS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=folder, suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(SERVER_ADDRESS.dump_json(address).decode())
        temporary.replace(server_file(data_dir, address))
    finally:
        temporary.unlink(missing_ok=True)


def withdraw_server(data_dir: Path, address: ServerAddress) -> None:
    server_file(data_dir, address).unlink(missing_ok=True)


def published_servers(data_dir: Path) -> list[ServerAddress]:
    found = [address for path in (data_dir / SERVERS_DIR).glob("*.json") if (address := _read_address(path)) is not None]
    return sorted(found, key=lambda address: (address.port != DEFAULT_PORT, address.port))


def _read_address(path: Path) -> ServerAddress | None:
    try:
        return SERVER_ADDRESS.validate_json(path.read_bytes())
    except (OSError, ValidationError):
        return None


class Probe(StrEnum):
    READY = "ready"
    OTHER_BUSSOLA = "other_bussola"
    CLOSED = "closed"
    WRONG = "wrong"
    SILENT = "silent"


def probe_server(address: ServerAddress) -> Probe:
    connection = _connect(address)
    if isinstance(connection, Probe):
        return connection
    try:
        connection.request("GET", HEALTH_PATH, headers={"Cookie": f"{token_cookie(address.port)}={address.token}"})
        response = connection.getresponse()
        status, body = response.status, response.read(MAX_PROBE_BODY)
    except TimeoutError:
        return Probe.SILENT
    except (OSError, http.client.HTTPException):
        return Probe.WRONG
    finally:
        connection.close()
    return _classify(status, body)


def _connect(address: ServerAddress) -> http.client.HTTPConnection | Probe:
    try:
        connection = http.client.HTTPConnection(address.host, address.port, timeout=HEALTH_TIMEOUT_SECONDS)
    except (ValueError, http.client.InvalidURL):
        return Probe.WRONG
    try:
        connection.connect()
    except OSError:
        connection.close()
        return Probe.CLOSED
    return connection


def _classify(status: int, body: bytes) -> Probe:
    if status == HTTPStatus.OK:
        return Probe.READY if _answer(body).app == APP_NAME else Probe.WRONG
    return Probe.OTHER_BUSSOLA if status == HTTPStatus.FORBIDDEN and _answer(body).code == INVALID_TOKEN_CODE else Probe.WRONG


class Answer(BaseModel):
    app: str | None = None
    code: str | None = None


def _answer(body: bytes) -> Answer:
    try:
        return Answer.model_validate_json(body)
    except ValidationError:
        return Answer()


def _socket_for(host: str) -> socket.socket:
    return socket.socket(socket.AF_INET6 if is_ipv6_host(host) else socket.AF_INET)


def free_port(host: str) -> int:
    with _socket_for(host) as probe:
        probe.bind((host, 0))
        return probe.getsockname()[1]


def port_is_free(host: str, port: int) -> bool:
    with _socket_for(host) as probe:
        probe.settimeout(HEALTH_TIMEOUT_SECONDS)
        if probe.connect_ex((host, port)) == 0:
            return False
    with _socket_for(host) as probe:
        if sys.platform != "win32":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def record_link_error(data_dir: Path, link: str, error: Exception) -> None:
    with contextlib.suppress(OSError):
        data_dir.mkdir(parents=True, exist_ok=True)
        log = data_dir / LINK_LOG_FILE
        mode = "w" if log.is_file() and log.stat().st_size > MAX_LINK_LOG_BYTES else "a"
        with log.open(mode, encoding="utf-8") as file:
            file.write(f"{datetime.now(UTC).isoformat(timespec='seconds')} {link[:MAX_LOGGED_LINK]!r}: {error}\n")


class PublishedServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, data_dir: Path, address: ServerAddress) -> None:
        super().__init__(config)
        self.data_dir = data_dir
        self.address = address

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets)
        if self.should_exit:
            return
        try:
            publish_server(self.data_dir, self.address)
        except OSError as error:
            logger.warning("bussola:// links will not find this server: %s", error)

    async def shutdown(self, sockets: list[socket.socket] | None = None) -> None:
        with contextlib.suppress(OSError):
            withdraw_server(self.data_dir, self.address)
        await super().shutdown(sockets)


def run_published(app: Any, data_dir: Path, address: ServerAddress) -> None:
    config = uvicorn.Config(app, host=address.host, port=address.port, log_level="warning")
    with contextlib.suppress(KeyboardInterrupt):
        PublishedServer(config, data_dir, address.reachable()).run()


class Process(Protocol):
    def poll(self) -> int | None: ...


def start_server(address: ServerAddress, environment: Mapping[str, str]) -> Process:
    command = [sys.executable, *BUSSOLA_MODULE, "serve", "--no-open", "--no-register", "--host", address.host, "--port", str(address.port)]
    return subprocess.Popen(
        command,
        env={**os.environ, **environment, TOKEN_ENV: address.token},
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
    start: Callable[[ServerAddress, Mapping[str, str]], Process] = start_server
    probe: Callable[[ServerAddress], Probe] = probe_server
    open_browser: Callable[[str], bool] = webbrowser.open
    sleep: Callable[[float], object] = time.sleep
    timeout: float = START_TIMEOUT_SECONDS
    exit_grace: float = EXIT_GRACE_SECONDS
    silent_grace: float = SILENT_GRACE_SECONDS
    port_free: Callable[[str, int], bool] = port_is_free
    search_path: str | None = None

    def open(self, link: str) -> str:
        path = browser_path(parse_link(link))
        url = self.ensure_server().url(path)
        if not self.open_browser(url):
            raise ServerStartError("bussola is running, but no browser could be opened. Open bussola from the link `bussola serve` prints.")
        return url

    def ensure_server(self) -> ServerAddress:
        with ThreadPoolExecutor() as pool:
            states = self._probe_all(pool)
            silent = [address for address, state in states.items() if state == Probe.SILENT and is_local_host(address.host)]
            found = self._first_ready(states) or (self._wait_for_silent(pool, silent) if silent else None)
            if found is not None:
                return found
            for port in (DEFAULT_PORT, *[None] * FREE_PORT_ATTEMPTS):
                address = ServerAddress(DEFAULT_HOST, port or free_port(DEFAULT_HOST), new_token())
                process = self.start(address, self._server_environment()) if self.port_free(address.host, address.port) else None
                found = self._wait_for_server(pool, address, process, set(silent))
                if found is not None:
                    return found
                if process is not None and self.port_free(address.host, address.port):
                    break
        raise ServerStartError("bussola did not start. Run `bussola serve` to see why.")

    def _server_environment(self) -> dict[str, str]:
        return {DATA_DIR_ENV: str(self.data_dir), **({"PATH": self.search_path} if self.search_path else {})}

    def _probe_all(self, pool: ThreadPoolExecutor, *extra: ServerAddress, skip: Set[ServerAddress] = NOTHING_TO_SKIP) -> dict[ServerAddress, Probe]:
        published = [address for address in published_servers(self.data_dir) if address not in skip]
        candidates = list(dict.fromkeys([*extra, *published]))
        states = dict(zip(candidates, pool.map(self.probe, candidates), strict=True))
        for candidate in published:
            state = states[candidate]
            if state in (Probe.CLOSED, Probe.WRONG, Probe.OTHER_BUSSOLA) or (state == Probe.SILENT and not is_local_host(candidate.host)):
                self._forget(candidate)
        return states

    def _wait_for_silent(self, pool: ThreadPoolExecutor, silent: list[ServerAddress]) -> ServerAddress | None:
        deadline = time.monotonic() + min(self.timeout, self.silent_grace)
        while silent and time.monotonic() < deadline:
            self.sleep(POLL_INTERVAL_SECONDS)
            states = dict(zip(silent, pool.map(self.probe, silent), strict=True))
            found = self._first_ready(states)
            if found is not None:
                return found
            for address in silent:
                if states[address] != Probe.SILENT:
                    self._forget(address)
            silent = [address for address in silent if states[address] == Probe.SILENT]
        return None

    def _forget(self, address: ServerAddress) -> None:
        with contextlib.suppress(OSError):
            withdraw_server(self.data_dir, address)

    def _first_ready(self, states: dict[ServerAddress, Probe]) -> ServerAddress | None:
        return next((candidate for candidate, state in states.items() if state == Probe.READY), None)

    def _wait_for_server(self, pool: ThreadPoolExecutor, started: ServerAddress, process: Process | None, tried: set[ServerAddress]) -> ServerAddress | None:
        deadline = time.monotonic() + self.timeout
        while True:
            states = self._probe_all(pool, started, skip=tried)
            found = self._first_ready(states)
            if found is not None:
                return found
            tried.update(address for address, state in states.items() if address != started and state != Probe.SILENT)
            exited = process is None or process.poll() is not None
            if exited and states[started] != Probe.OTHER_BUSSOLA:
                return None
            if exited:
                deadline = min(deadline, time.monotonic() + self.exit_grace)
            if time.monotonic() >= deadline:
                if not exited:
                    raise ServerStartError(f"bussola is still starting on {host_port(started.host, started.port)}. Open the link again in a moment.")
                return None
            self.sleep(POLL_INTERVAL_SECONDS)
