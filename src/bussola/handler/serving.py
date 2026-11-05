import contextlib
import logging
import socket
from pathlib import Path
from typing import Any

import uvicorn

from bussola.handler.server import ServerAddress, publish_server, withdraw_server

logger = logging.getLogger(__name__)


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
