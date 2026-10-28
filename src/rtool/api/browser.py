from urllib.parse import urlparse

from fastapi import APIRouter, Request
from pydantic import BaseModel

from rtool.api.state import app_state
from rtool.errors import InvalidRequestError

ALLOWED_SCHEME = "https"
ALLOWED_HOSTS = frozenset({"github.com"})

router = APIRouter(tags=["browser"])


class OpenUrlIn(BaseModel):
    url: str


class OpenUrlOut(BaseModel):
    opened: bool


@router.post("/open-url")
def open_url(body: OpenUrlIn, request: Request) -> OpenUrlOut:
    parsed = urlparse(body.url)
    if parsed.scheme != ALLOWED_SCHEME or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password:
        raise InvalidRequestError("Only https://github.com links can be opened from rtool")
    app_state(request).url_opener(body.url)
    return OpenUrlOut(opened=True)
