from pathlib import Path

from fastapi import APIRouter, Request

from bussola.ai.base import AiError, Cancellation
from bussola.ai.config import AiSettings
from bussola.ai.connection import check_connection
from bussola.ai.settings import load_ai_settings
from bussola.api.deps import RepoDep
from bussola.api.schemas import AiStatusOut, AiTestOut
from bussola.api.state import AppState, app_state

router = APIRouter(tags=["ai"])


@router.get("/ai")
def get_ai(request: Request) -> AiStatusOut:
    return _status(app_state(request), None)


@router.get("/repos/{repo_id}/ai")
def get_repo_ai(repo: RepoDep, request: Request) -> AiStatusOut:
    return _status(app_state(request), Path(repo.path))


@router.post("/ai/test")
def test_ai(request: Request) -> AiTestOut:
    state = app_state(request)
    try:
        provider = state.ai_factory(load_ai_settings(state.settings.config_file))
    except AiError as error:
        return AiTestOut(ok=False, message=str(error), elapsed_ms=0)
    result = check_connection(provider, Cancellation())
    return AiTestOut(ok=result.ok, message=result.message, elapsed_ms=result.elapsed_ms)


def _status(state: AppState, repo_root: Path | None) -> AiStatusOut:
    config_file = str(state.settings.config_file) if state.settings.config_file else None
    try:
        settings = load_ai_settings(state.settings.config_file, repo_root)
    except AiError as error:
        return AiStatusOut(configured=False, problem=str(error), config_file=config_file)
    return AiStatusOut(
        configured=settings.configured,
        provider=settings.provider if settings.configured else None,
        label=settings.label if settings.configured else None,
        model=settings.model,
        endpoint=settings.endpoint,
        source=settings.source,
        api_key_env=settings.api_key_env,
        api_key_set=settings.api_key() is not None,
        problem=_problem(state, settings),
        config_file=config_file,
        target=settings.target if settings.configured else None,
    )


def _problem(state: AppState, settings: AiSettings) -> str | None:
    if not settings.configured:
        return None
    try:
        state.ai_factory(settings)
    except AiError as error:
        return str(error)
    return None
