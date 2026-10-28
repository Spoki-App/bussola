from fastapi import APIRouter

from rtool.api.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> HealthOut:
    return HealthOut(status="ok")
