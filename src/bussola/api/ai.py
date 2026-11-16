from dataclasses import asdict, replace
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Request
from fastapi import Path as PathParameter

from bussola.ai.base import AiError, AiProvider, Cancellation
from bussola.ai.config import (
    AiOperation,
    AiOperations,
    AiPrompts,
    AiSettings,
    UserAiConfig,
    describe_config_error,
    load_user_config,
    save_user_ai_config,
)
from bussola.ai.connection import CONNECTION_TIMEOUT_SECONDS, check_connection
from bussola.ai.settings import load_ai_settings
from bussola.api.deps import RepoDep
from bussola.api.schemas import (
    MAX_CALL_ID_LENGTH,
    AiConfigIn,
    AiConfigOut,
    AiModelOut,
    AiModelsOut,
    AiOperationOut,
    AiPromptOut,
    AiPromptsIn,
    AiPromptsOut,
    AiStatusOut,
    AiTestOut,
    CancelOut,
)
from bussola.api.state import AppState, app_state
from bussola.errors import ConflictError, InvalidRequestError
from bussola.review.ai_review import REVIEW_PROMPT
from bussola.review.descriptions import DESCRIBE_PROMPT, IMPACT_PROMPT

router = APIRouter(tags=["ai"])
OPERATIONS = {
    AiOperation.DESCRIBE: "Describe",
    AiOperation.IMPACT: "Rate impact",
    AiOperation.REVIEW: "AI review",
    AiOperation.CHAT: "AI chat",
}
PROMPTS = {
    "describe": (OPERATIONS[AiOperation.DESCRIBE], DESCRIBE_PROMPT.default),
    "impact": (OPERATIONS[AiOperation.IMPACT], IMPACT_PROMPT.default),
    "review": (OPERATIONS[AiOperation.REVIEW], REVIEW_PROMPT.default),
}


@router.get("/ai")
def get_ai(request: Request) -> AiStatusOut:
    return _status(app_state(request), None)


@router.get("/repos/{repo_id}/ai")
def get_repo_ai(repo: RepoDep, request: Request) -> AiStatusOut:
    return _status(app_state(request), Path(repo.path))


@router.get("/ai/config")
def get_ai_config(request: Request) -> AiConfigOut:
    config_file = app_state(request).settings.config_file
    shown = str(config_file) if config_file else None
    try:
        ai = load_user_config(config_file).ai
    except AiError as error:
        return AiConfigOut(config_file=shown, problem=str(error))
    return AiConfigOut(**ai.model_dump(mode="json"), config_file=shown)


@router.put("/ai/config")
def put_ai_config(body: AiConfigIn, request: Request) -> AiStatusOut:
    state = app_state(request)
    config_file = state.settings.config_file
    if config_file is None:
        raise ConflictError("bussola was started without a configuration file, so the AI settings cannot be saved")
    try:
        current = load_user_config(config_file).ai
    except AiError:
        current = UserAiConfig()
    kept = current.model_dump(exclude=set(AiConfigIn.model_fields))
    try:
        save_user_ai_config(config_file, UserAiConfig.model_validate(kept | body.model_dump(exclude_none=True)))
    except OSError as error:
        raise ConflictError(f"Could not save {config_file}: {error}") from error
    except ValueError as error:
        raise InvalidRequestError(describe_config_error(error)) from error
    return _status(state, None)


@router.get("/ai/prompts")
def get_ai_prompts(request: Request) -> AiPromptsOut:
    config_file = app_state(request).settings.config_file
    shown = str(config_file) if config_file else None
    try:
        prompts = load_user_config(config_file).ai.prompts
    except AiError as error:
        return AiPromptsOut(prompts=_prompts_out(AiPrompts()), config_file=shown, problem=str(error))
    return AiPromptsOut(prompts=_prompts_out(prompts), config_file=shown)


@router.put("/ai/prompts")
def put_ai_prompts(body: AiPromptsIn, request: Request) -> AiPromptsOut:
    config_file = app_state(request).settings.config_file
    if config_file is None:
        raise ConflictError("bussola was started without a configuration file, so the AI prompts cannot be saved")
    try:
        current = load_user_config(config_file).ai
    except AiError as error:
        raise ConflictError(f"Fix the configuration file before changing the prompts: {error}") from error
    chosen = {name: None if text is None or text.strip() == PROMPTS[name][1].strip() else text for name, text in body.model_dump().items()}
    try:
        save_user_ai_config(config_file, current.model_copy(update={"prompts": AiPrompts.model_validate(chosen)}))
    except OSError as error:
        raise ConflictError(f"Could not save {config_file}: {error}") from error
    except ValueError as error:
        raise InvalidRequestError(describe_config_error(error)) from error
    return get_ai_prompts(request)


@router.put("/ai/operations")
def put_ai_operations(body: AiOperations, request: Request) -> AiStatusOut:
    state = app_state(request)
    config_file = state.settings.config_file
    if config_file is None:
        raise ConflictError("bussola was started without a configuration file, so the AI models cannot be saved")
    try:
        current = load_user_config(config_file).ai
    except AiError as error:
        raise ConflictError(f"Fix the configuration file before changing the AI models: {error}") from error
    try:
        save_user_ai_config(config_file, current.model_copy(update={"operations": body}))
    except OSError as error:
        raise ConflictError(f"Could not save {config_file}: {error}") from error
    except ValueError as error:
        raise InvalidRequestError(describe_config_error(error)) from error
    return _status(state, None)


@router.get("/ai/models")
def list_ai_models(request: Request) -> AiModelsOut:
    state = app_state(request)
    try:
        settings = load_ai_settings(state.settings.config_file)
        if not settings.configured:
            return AiModelsOut()
        models = _quick_provider(state, settings).models(Cancellation())
    except AiError as error:
        return AiModelsOut(problem=str(error))
    return AiModelsOut(models=[AiModelOut(id=model.id, effort=model.effort) for model in models])


@router.post("/ai/test")
def test_ai(request: Request) -> AiTestOut:
    state = app_state(request)

    def connect() -> AiProvider:
        return _quick_provider(state, load_ai_settings(state.settings.config_file))

    return AiTestOut(**asdict(check_connection(connect, Cancellation())))


@router.post("/ai/calls/{call_id}/cancel")
async def cancel_call(call_id: Annotated[str, PathParameter(max_length=MAX_CALL_ID_LENGTH)], request: Request) -> CancelOut:
    return CancelOut(cancelled=app_state(request).ai_calls.cancel(call_id))


def _quick_provider(state: AppState, settings: AiSettings) -> AiProvider:
    return state.ai_factory(replace(settings, timeout=min(settings.timeout, CONNECTION_TIMEOUT_SECONDS)))


def _prompts_out(prompts: AiPrompts) -> list[AiPromptOut]:
    custom = prompts.custom()
    return [AiPromptOut(key=key, title=title, default=default, custom=custom.get(key)) for key, (title, default) in PROMPTS.items()]


def _operations_out(operations: AiOperations) -> list[AiOperationOut]:
    return [AiOperationOut(key=key, title=title, **operations.of(key).model_dump(mode="json")) for key, title in OPERATIONS.items()]


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
        api_key_env=settings.api_key_env,
        api_key_set=settings.api_key() is not None,
        problem=_problem(state, settings),
        config_file=config_file,
        target=settings.target,
        operations=_operations_out(settings.operations),
    )


def _problem(state: AppState, settings: AiSettings) -> str | None:
    if not settings.configured:
        return None
    try:
        state.ai_factory(settings)
    except AiError as error:
        return str(error)
    return None
