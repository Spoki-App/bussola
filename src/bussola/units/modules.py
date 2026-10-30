from collections.abc import Callable
from pathlib import PurePosixPath

from bussola.units.extractors.go import GoExtractor
from bussola.units.extractors.javascript import JAVASCRIPT
from bussola.units.extractors.typescript import TSX, TYPESCRIPT
from bussola.units.registry import PYTHON, extractor_for

GO_MOD = "go.mod"
PYTHON_SOURCE_ROOT = "src"
PYTHON_PACKAGE_FILE = "__init__"
SCRIPT_EXTRACTORS = (TYPESCRIPT, TSX, JAVASCRIPT)

GoModuleLookup = Callable[[str], str | None]


def module_path(path: str, go_module: GoModuleLookup) -> str | None:
    extractor = extractor_for(path)
    file = PurePosixPath(path)
    if extractor is PYTHON:
        return _python_module(file)
    if extractor in SCRIPT_EXTRACTORS:
        return str(file.with_suffix(""))
    if isinstance(extractor, GoExtractor):
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
        name = go_module("/".join(root.parts))
        if name is not None:
            return "/".join((name, *directory.relative_to(root).parts))
    return "/".join(directory.parts) or None
