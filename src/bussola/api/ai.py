import asyncio
from dataclasses import asdict, replace
from pathlib import Path
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

from bussola.ai.base import AiError, AiProvider, Cancellation
from bussola.ai.config import AiSettings
from bussola.ai.connection import CONNECTION_TIMEOUT_SECONDS, check_connection
from bussola.ai.settings import load_ai_settings
from bussola.api.deps import RepoDep
from bussola.api.schemas import AiStatusOut, AiTestOut
from bussola.api.state import AppState, app_state

router = APIRouter(tags=["ai"])
DISCONNECT_POLL_SECONDS = 0.5


@router.get("/ai")
def get_ai(request: Request) -> AiStatusOut:
    return _status(app_state(request), None)


@router.get("/repos/{repo_id}/ai")
def get_repo_ai(repo: RepoDep, request: Request) -> AiStatusOut:
    return _status(app_state(request), Path(repo.path))


@router.post("/ai/test")
async def test_ai(request: Request) -> AiTestOut:
    state = app_state(request)
    cancellation = Cancellation()

    def connect() -> AiProvider:
        settings = load_ai_settings(state.settings.config_file)
        return state.ai_factory(replace(settings, timeout=min(settings.timeout, CONNECTION_TIMEOUT_SECONDS)))

    watcher = asyncio.create_task(cancel_on_disconnect(request, cancellation))
    try:
        result = await run_in_threadpool(check_connection, connect, cancellation)
    finally:
        watcher.cancel()
    return AiTestOut(**asdict(result))


class ClientConnection(Protocol):
    async def is_disconnected(self) -> bool: ...


async def cancel_on_disconnect(request: ClientConnection, cancellation: Cancellation) -> None:
    while not await request.is_disconnected():
        await asyncio.sleep(DISCONNECT_POLL_SECONDS)
    cancellation.cancel()


def _status(state: AppState, repo_root: Path | None) -> AiStatusOut:
    config_file = str(state.settings.config_file) if state.settings.config_file else None
    try:
        settings = load_ai_settings(state.settings.config_file, repo_root)
    except AiError as error:
        return AiStatusOut(configured=False, problem=str(error), config_file=config_file)
    return AiStatusOut(
        configured=settings.configured,
        provider=settings.provider if settings.configured else None,
        label=settings.label,
        model=settings.model,
        endpoint=settings.endpoint,
        source=settings.source,
        api_key_env=settings.api_key_env,
        api_key_set=settings.api_key() is not None,
        problem=_problem(state, settings),
        config_file=config_file,
        target=settings.target,
    )


def _problem(state: AppState, settings: AiSettings) -> str | None:
    if not settings.configured:
        return None
    try:
        state.ai_factory(settings)
    except AiError as error:
        return str(error)
    return None
