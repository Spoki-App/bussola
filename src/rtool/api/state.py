from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from fastapi import FastAPI, Request

from rtool.config import AppSettings
from rtool.forge.base import ForgeAdapter
from rtool.identity import GitConfigIdentity
from rtool.storage.database import Database


@dataclass(frozen=True)
class AppState:
    settings: AppSettings
    database: Database
    identity: GitConfigIdentity
    forge: ForgeAdapter
    url_opener: Callable[[str], object]


def attach_state(app: FastAPI, state: AppState) -> None:
    app.state.rtool = state


def app_state(request: Request) -> AppState:
    return cast(AppState, request.app.state.rtool)
