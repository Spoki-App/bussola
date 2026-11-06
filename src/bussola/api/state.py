from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from fastapi import FastAPI, Request

from bussola.ai.base import AiProvider
from bussola.ai.calls import RunningCalls
from bussola.ai.config import AiSettings
from bussola.config import AppSettings
from bussola.forge.base import ForgeAdapter
from bussola.identity import GitConfigIdentity
from bussola.navigation.navigator import Navigator
from bussola.review.ai_review import RunningReviews
from bussola.storage.ai_cache import DatabaseAiCache
from bussola.storage.database import Database


@dataclass(frozen=True)
class AppState:
    settings: AppSettings
    database: Database
    identity: GitConfigIdentity
    forge: ForgeAdapter
    url_opener: Callable[[str], object]
    navigator: Navigator
    ai_factory: Callable[[AiSettings], AiProvider]
    ai_calls: RunningCalls = field(default_factory=RunningCalls)
    ai_reviews: RunningReviews = field(default_factory=RunningReviews)

    @property
    def ai_cache(self) -> DatabaseAiCache:
        return DatabaseAiCache(self.database)


def attach_state(app: FastAPI, state: AppState) -> None:
    app.state.bussola = state


def app_state(request: Request) -> AppState:
    return cast(AppState, request.app.state.bussola)
