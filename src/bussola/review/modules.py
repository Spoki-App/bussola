from functools import lru_cache
from pathlib import Path, PurePosixPath

from bussola.git import GitRepo
from bussola.storage.models import Repo
from bussola.units.modules import GO_MOD, go_module_name, module_path

GO_MODULE_CACHE_SIZE = 1024


class ModulePaths:
    def __init__(self, repo: Repo, commit: str) -> None:
        self._root = repo.path
        self._commit = commit

    def of(self, path: str | None) -> str | None:
        return None if path is None else module_path(path, self._go_module)

    def _go_module(self, directory: str) -> str | None:
        if not Path(self._root).is_dir():
            return None
        return _go_module_at(self._root, self._commit, str(PurePosixPath(directory, GO_MOD)))


@lru_cache(maxsize=GO_MODULE_CACHE_SIZE)
def _go_module_at(root: str, commit: str, go_mod: str) -> str | None:
    data = GitRepo(Path(root)).file_at(commit, go_mod)
    return None if data is None else go_module_name(data)
