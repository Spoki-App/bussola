from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from rtool.api import API_PREFIX, build_api_router
from rtool.config import STATIC_DIR

INDEX_FILE = "index.html"
ASSETS_DIR = "assets"


def create_app(static_dir: Path = STATIC_DIR) -> FastAPI:
    app = FastAPI(title="rtool", docs_url=None, redoc_url=None)
    app.include_router(build_api_router())
    _mount_frontend(app, static_dir)
    return app


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
        return FileResponse(root_files.get(path, index))
