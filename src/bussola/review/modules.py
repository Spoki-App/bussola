from functools import lru_cache
from pathlib import Path, PurePosixPath

from bussola.errors import ConflictError
from bussola.git import GitRepo
from bussola.review.repos import open_repo
from bussola.storage.models import Repo, Revision
from bussola.units.modules import GO_MOD, go_module_name, is_go_source, module_path

GO_TREE_CACHE_SIZE = 8


class GoTree:
    def __init__(self, git: GitRepo, commit: str) -> None:
        paths = git.tree_paths(commit)
        self.sources = frozenset(path for path in paths if is_go_source(path))
        self._go_mods = frozenset(path for path in paths if PurePosixPath(path).name == GO_MOD)
        self._git = git
        self._commit = commit
        self._names: dict[str, str | None] = {}

    def module(self, directory: str) -> str | None:
        go_mod = str(PurePosixPath(directory, GO_MOD))
        if go_mod not in self._go_mods:
            return None
        if go_mod not in self._names:
            data = self._git.file_at(self._commit, go_mod)
            self._names[go_mod] = None if data is None else go_module_name(data)
        return self._names[go_mod]


class ModulePaths:
    def __init__(self, repo: Repo, revision: Revision) -> None:
        try:
            self._root: str | None = str(open_repo(repo).root)
        except ConflictError:
            self._root = None
        self._head = revision.head_sha
        self._base = revision.merge_base_sha

    def of(self, path: str | None) -> str | None:
        return None if path is None else module_path(path, lambda directory: self._go_module(path, directory))

    def _go_module(self, path: str, directory: str) -> str | None:
        if self._root is None:
            return None
        head = _go_tree(self._root, self._head)
        tree = head if path in head.sources else _go_tree(self._root, self._base)
        return tree.module(directory)


@lru_cache(maxsize=GO_TREE_CACHE_SIZE)
def _go_tree(root: str, commit: str) -> GoTree:
    return GoTree(GitRepo(Path(root)), commit)
