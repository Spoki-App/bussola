import ipaddress
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
INVALID_TOKEN_DETAIL = "Missing or invalid session token"
INVALID_TOKEN_CODE = "invalid_token"

type CallNext = Callable[[Request], Awaitable[Response]]


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_cookie(port: int | None) -> str:
    return f"{TOKEN_COOKIE}_{port}" if port else TOKEN_COOKIE


def is_local_host(host: str) -> bool:
    if host in LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_ipv6_host(host: str) -> bool:
    return ":" in host


def host_port(host: str, port: int) -> str:
    return f"[{host}]:{port}" if is_ipv6_host(host) else f"{host}:{port}"


def allowed_hosts_for(host: str, port: int) -> frozenset[str]:
    return frozenset(host_port(name, port) for name in {*LOCAL_HOSTS, host})


def install_security(app: FastAPI, settings: AppSettings) -> None:
    @app.middleware("http")
    async def guard(request: Request, call_next: CallNext) -> Response:
        if settings.allowed_hosts and request.headers.get("host", "") not in settings.allowed_hosts:
            return JSONResponse({"detail": "Host not allowed"}, status_code=status.HTTP_403_FORBIDDEN)
        if settings.token is None:
            return await call_next(request)
        query_token = request.query_params.get(TOKEN_QUERY)
        if query_token is not None and _same_token(query_token, settings.token):
            return _store_token_and_redirect(request, settings.token, token_cookie(settings.port))
        cookie = request.cookies.get(token_cookie(settings.port), "")
        if request.url.path.startswith(API_PATH_PREFIX) and not _same_token(cookie, settings.token):
            return JSONResponse({"detail": INVALID_TOKEN_DETAIL, "code": INVALID_TOKEN_CODE}, status_code=status.HTTP_403_FORBIDDEN)
        return await call_next(request)


def _same_token(given: str, token: str) -> bool:
    return secrets.compare_digest(given.encode(), token.encode())


def _store_token_and_redirect(request: Request, token: str, cookie: str) -> Response:
    remaining = [(key, value) for key, value in request.query_params.multi_items() if key != TOKEN_QUERY]
    target = request.url.path + (f"?{urlencode(remaining)}" if remaining else "")
    response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(cookie, token, httponly=True, samesite="strict", path="/")
    return response
