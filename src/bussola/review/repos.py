from pathlib import Path

from bussola.errors import ConflictError, InvalidRequestError
from bussola.git import GitError, GitRepo
from bussola.storage.models import Repo
from bussola.storage.repositories import Store


def register_repo(store: Store, path: Path) -> Repo:
    try:
        git_repo = GitRepo.discover(path.expanduser())
        root_commit = git_repo.first_commit()
    except (GitError, OSError) as error:
        raise InvalidRequestError(f"{path} is not a git repository with at least one commit") from error
    root = str(git_repo.root.resolve())
    existing = store.reviews.find_repo_by_path(root)
    if existing is not None:
        return existing
    moved = store.reviews.find_repo_by_root(root_commit)
    if moved is not None and not Path(moved.path).exists():
        moved.path = root
        return moved
    return store.reviews.add_repo(Repo(path=root, root_commit=root_commit))


def open_repo(repo: Repo) -> GitRepo:
    root = Path(repo.path)
    if not root.is_dir():
        raise ConflictError(f"Repository not found at {repo.path}. Register it again from its new location.")
    return GitRepo(root)
