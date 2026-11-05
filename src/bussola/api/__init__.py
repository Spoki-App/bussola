from fastapi import APIRouter

from bussola.api import ai, ai_review, approvals, browser, descriptions, directories, forge, health, navigation, pulls, repos, reviews, threads, units

API_PREFIX = "/api"


def build_api_router() -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)
    for module in (health, browser, repos, directories, pulls, reviews, units, approvals, threads, forge, navigation, ai, descriptions, ai_review):
        router.include_router(module.router)
    return router
