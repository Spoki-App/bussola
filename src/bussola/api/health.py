from fastapi import APIRouter

from bussola.api.schemas import HealthOut
from bussola.config import APP_NAME

router = APIRouter(tags=["health"])


@router.get("/health")
async def get_health() -> HealthOut:
    return HealthOut(status="ok", app=APP_NAME)
