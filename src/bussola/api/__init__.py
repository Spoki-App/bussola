from fastapi import APIRouter

from bussola.api import (
    ai,
    ai_review,
    approvals,
    attachments,
    browser,
    descriptions,
    directories,
    editor_themes,
    forge,
    health,
    navigation,
    pulls,
    repos,
    reviews,
    threads,
    units,
)

API_PREFIX = "/api"


def build_api_router() -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)
    modules = (
        health,
        attachments,
        browser,
        repos,
        directories,
        editor_themes,
        pulls,
        reviews,
        units,
        approvals,
        threads,
        forge,
        navigation,
        ai,
        descriptions,
        ai_review,
    )
    for module in modules:
        router.include_router(module.router)
    return router
