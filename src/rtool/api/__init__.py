from fastapi import APIRouter

from rtool.api import health

API_PREFIX = "/api"


def build_api_router() -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)
    router.include_router(health.router)
    return router
