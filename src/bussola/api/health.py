from fastapi import APIRouter

from bussola.api.schemas import HealthOut
from bussola.storage.database import APP_NAME

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> HealthOut:
    return HealthOut(status="ok", app=APP_NAME)
