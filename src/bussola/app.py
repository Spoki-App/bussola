import webbrowser
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bussola.api import API_PREFIX, build_api_router
from bussola.api.state import AppState, attach_state
from bussola.config import AppSettings
from bussola.errors import ConflictError, DomainError, ForbiddenError, InvalidRequestError, NotFoundError
from bussola.forge.base import ForgeAdapter, ForgeError
from bussola.forge.github import GitHubAdapter
from bussola.git import GitError, InvalidRefError
from bussola.identity import GitConfigIdentity
from bussola.review.refs import NoBaseBranchError
from bussola.security import install_security
from bussola.storage.database import Database

INDEX_FILE = "index.html"
REVALIDATE = {"Cache-Control": "no-cache"}
ASSETS_DIR = "assets"
ERROR_STATUS: dict[type[Exception], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
    InvalidRequestError: status.HTTP_400_BAD_REQUEST,
    InvalidRefError: status.HTTP_400_BAD_REQUEST,
    NoBaseBranchError: status.HTTP_400_BAD_REQUEST,
    GitError: status.HTTP_400_BAD_REQUEST,
    ForgeError: status.HTTP_502_BAD_GATEWAY,
}


def create_app(settings: AppSettings, forge: ForgeAdapter | None = None, url_opener: Callable[[str], object] | None = None) -> FastAPI:
    app = FastAPI(title="bussola", docs_url=None, redoc_url=None, openapi_url=None)
    database = Database.open(settings.data_dir)
    state = AppState(settings, database, GitConfigIdentity(settings.identity_dir), forge or GitHubAdapter(), url_opener or webbrowser.open_new_tab)
    attach_state(app, state)
    for error_type in ERROR_STATUS:
        app.add_exception_handler(error_type, _handle_error)
    install_security(app, settings)
    app.include_router(build_api_router())
    _mount_frontend(app, settings.static_dir)
    return app


async def _handle_error(_request: Request, error: Exception) -> JSONResponse:
    code = next((code for error_type, code in ERROR_STATUS.items() if isinstance(error, error_type)), status.HTTP_500_INTERNAL_SERVER_ERROR)
    error_code = error.code if isinstance(error, DomainError) else None
    return JSONResponse({"detail": str(error)} | ({"code": error_code} if error_code else {}), status_code=code)


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    assets = static_dir / ASSETS_DIR
    if assets.is_dir():
        app.mount(f"/{ASSETS_DIR}", StaticFiles(directory=assets), name=ASSETS_DIR)
    root_files = {entry.name: entry for entry in static_dir.iterdir() if entry.is_file()} if static_dir.is_dir() else {}
    index = root_files.get(INDEX_FILE)

    @app.get("/{path:path}", include_in_schema=False)
    def serve_frontend(path: str) -> FileResponse:
        if path.startswith(API_PREFIX.lstrip("/")) or index is None:
            raise HTTPException(status_code=404)
        return FileResponse(root_files.get(path, index), headers=REVALIDATE)
