from fastapi import APIRouter

from bussola.api import ai, approvals, browser, directories, forge, health, pulls, repos, reviews, threads, units

API_PREFIX = "/api"


def build_api_router() -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)
    for module in (health, browser, repos, directories, pulls, reviews, units, approvals, threads, forge, ai):
        router.include_router(module.router)
    return router
