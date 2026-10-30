from dataclasses import asdict

from fastapi import APIRouter

from bussola.api.deps import StoreDep
from bussola.api.schemas import DirectoryListingOut, FoundRepositoryOut, RepositoryScanOut
from bussola.directories import find_repositories, list_directories

router = APIRouter(tags=["directories"])


@router.get("/directories")
def get_directories(path: str | None = None) -> DirectoryListingOut:
    return DirectoryListingOut.model_validate(asdict(list_directories(path)))


@router.get("/directories/repositories")
def scan_repositories(store: StoreDep) -> RepositoryScanOut:
    scan = find_repositories()
    registered = {repo.path for repo in store.reviews.list_repos()}
    repositories = [FoundRepositoryOut(name=repo.name, path=repo.path, registered=repo.path in registered) for repo in scan.repositories]
    return RepositoryScanOut(root=scan.root, repositories=repositories, truncated=scan.truncated)
