import secrets
from collections.abc import Awaitable, Callable
from urllib.parse import urlencode

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from bussola.config import AppSettings

TOKEN_COOKIE = "bussola_token"
TOKEN_QUERY = "token"
TOKEN_ENV = "BUSSOLA_TOKEN"
API_PATH_PREFIX = "/api/"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")

type CallNext = Callable[[Request], Awaitable[Response]]


def new_token() -> str:
    return secrets.token_urlsafe(32)


def allowed_hosts_for(host: str, port: int) -> frozenset[str]:
    return frozenset(f"[{name}]:{port}" if ":" in name else f"{name}:{port}" for name in {*LOCAL_HOSTS, host})


def install_security(app: FastAPI, settings: AppSettings) -> None:
    @app.middleware("http")
    async def guard(request: Request, call_next: CallNext) -> Response:
        if settings.allowed_hosts and request.headers.get("host", "") not in settings.allowed_hosts:
            return JSONResponse({"detail": "Host not allowed"}, status_code=status.HTTP_403_FORBIDDEN)
        if settings.token is None:
            return await call_next(request)
        query_token = request.query_params.get(TOKEN_QUERY)
        if query_token is not None and secrets.compare_digest(query_token, settings.token):
            return _store_token_and_redirect(request, settings.token)
        if request.url.path.startswith(API_PATH_PREFIX) and not secrets.compare_digest(request.cookies.get(TOKEN_COOKIE, ""), settings.token):
            return JSONResponse({"detail": "Missing or invalid session token"}, status_code=status.HTTP_403_FORBIDDEN)
        return await call_next(request)


def _store_token_and_redirect(request: Request, token: str) -> Response:
    remaining = [(key, value) for key, value in request.query_params.multi_items() if key != TOKEN_QUERY]
    target = request.url.path + (f"?{urlencode(remaining)}" if remaining else "")
    response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(TOKEN_COOKIE, token, httponly=True, samesite="strict", path="/")
    return response
