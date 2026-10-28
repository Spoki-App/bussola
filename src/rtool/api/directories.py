from dataclasses import asdict

from fastapi import APIRouter

from rtool.api.schemas import DirectoryListingOut
from rtool.directories import list_directories

router = APIRouter(tags=["directories"])


@router.get("/directories")
def get_directories(path: str | None = None) -> DirectoryListingOut:
    return DirectoryListingOut.model_validate(asdict(list_directories(path)))
