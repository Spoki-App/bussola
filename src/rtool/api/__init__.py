from fastapi import APIRouter

from rtool.api import approvals, health, repos, reviews, threads, units

API_PREFIX = "/api"


def build_api_router() -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)
    for module in (health, repos, reviews, units, approvals, threads):
        router.include_router(module.router)
    return router
