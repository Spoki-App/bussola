from functools import lru_cache
from pathlib import Path, PurePosixPath

from bussola.errors import ConflictError
from bussola.git import GitRepo
from bussola.review.repos import open_repo
from bussola.storage.models import Repo
from bussola.units.modules import GO_MOD, go_module_name, module_path

GO_MODULE_CACHE_SIZE = 1024


class ModulePaths:
    def __init__(self, repo: Repo, commit: str) -> None:
        try:
            self._root: str | None = str(open_repo(repo).root)
        except ConflictError:
            self._root = None
        self._commit = commit

    def of(self, path: str | None) -> str | None:
        return None if path is None else module_path(path, self._go_module)

    def _go_module(self, directory: str) -> str | None:
        if self._root is None:
            return None
        return _go_module_at(self._root, self._commit, str(PurePosixPath(directory, GO_MOD)))


@lru_cache(maxsize=GO_MODULE_CACHE_SIZE)
def _go_module_at(root: str, commit: str, go_mod: str) -> str | None:
    data = GitRepo(Path(root)).file_at(commit, go_mod)
    return None if data is None else go_module_name(data)
