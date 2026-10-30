from collections.abc import Callable
from pathlib import PurePosixPath

PYTHON_SUFFIXES = frozenset({".py", ".pyi"})
SCRIPT_SUFFIXES = frozenset({".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"})
GO_SUFFIX = ".go"
GO_MOD = "go.mod"
PYTHON_SOURCE_ROOT = "src"
PYTHON_PACKAGE_FILE = "__init__"

GoModuleLookup = Callable[[str], str | None]


def module_path(path: str, go_module: GoModuleLookup) -> str | None:
    file = PurePosixPath(path)
    suffix = file.suffix.lower()
    if suffix in PYTHON_SUFFIXES:
        return _python_module(file)
    if suffix in SCRIPT_SUFFIXES:
        return str(file.with_suffix(""))
    if suffix == GO_SUFFIX:
        return _go_package(file.parent, go_module)
    return None


def go_module_name(go_mod: bytes) -> str | None:
    for line in go_mod.decode("utf-8", errors="replace").splitlines():
        words = line.split("//", 1)[0].split(maxsplit=1)
        if len(words) > 1 and words[0] == "module":
            return words[1].strip().strip('"`')
    return None


def _python_module(file: PurePosixPath) -> str | None:
    parts = list(file.with_suffix("").parts)
    if parts and parts[0] == PYTHON_SOURCE_ROOT:
        parts = parts[1:]
    if parts and parts[-1] == PYTHON_PACKAGE_FILE:
        parts = parts[:-1]
    return ".".join(parts) or None


def _go_package(directory: PurePosixPath, go_module: GoModuleLookup) -> str | None:
    for root in (directory, *directory.parents):
        name = go_module(_directory(root))
        if name is not None:
            relative = directory.relative_to(root)
            return name if relative == PurePosixPath() else f"{name}/{relative}"
    return _directory(directory) or None


def _directory(directory: PurePosixPath) -> str:
    return "" if directory == PurePosixPath() else str(directory)
