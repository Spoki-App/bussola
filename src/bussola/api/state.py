from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from fastapi import FastAPI, Request

from bussola.ai.base import AiProvider
from bussola.ai.config import AiSettings
from bussola.config import AppSettings
from bussola.forge.base import ForgeAdapter
from bussola.identity import GitConfigIdentity
from bussola.storage.database import Database


@dataclass(frozen=True)
class AppState:
    settings: AppSettings
    database: Database
    identity: GitConfigIdentity
    forge: ForgeAdapter
    url_opener: Callable[[str], object]
    ai_factory: Callable[[AiSettings], AiProvider]


def attach_state(app: FastAPI, state: AppState) -> None:
    app.state.bussola = state


def app_state(request: Request) -> AppState:
    return cast(AppState, request.app.state.bussola)
