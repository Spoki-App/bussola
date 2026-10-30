from collections.abc import Callable
from pathlib import PurePosixPath

from bussola.units.extractors.javascript import JAVASCRIPT
from bussola.units.extractors.typescript import TSX, TYPESCRIPT
from bussola.units.registry import GO, PYTHON, extractor_for

GO_MOD = "go.mod"
GO_VENDOR = "vendor"
PYTHON_SOURCE_ROOT = "src"
PYTHON_PACKAGE_FILE = "__init__"
SCRIPT_EXTRACTORS = (TYPESCRIPT, TSX, JAVASCRIPT)
GO_BLOCK_DELIMITERS = frozenset({"(", ")"})

GoModuleLookup = Callable[[str], str | None]


def module_path(path: str, go_module: GoModuleLookup) -> str | None:
    extractor = extractor_for(path)
    file = PurePosixPath(path)
    if extractor is PYTHON:
        return _python_module(file)
    if extractor in SCRIPT_EXTRACTORS:
        return str(file.with_suffix(""))
    if extractor is GO:
        return _go_package(file.parent, go_module)
    return None


def is_go_source(path: str) -> bool:
    return extractor_for(path) is GO


def go_module_name(go_mod: bytes) -> str | None:
    lines = [words for line in go_mod.decode("utf-8", errors="replace").splitlines() if (words := line.split("//", 1)[0].split())]
    for index, words in enumerate(lines):
        if words[0] != "module":
            continue
        names = lines[index + 1] if words[1:] == ["("] and index + 1 < len(lines) else words[1:]
        if names and names[0] not in GO_BLOCK_DELIMITERS:
            return names[0].strip('"`')
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
        if name is None:
            continue
        relative = directory.relative_to(root).parts
        if relative[:1] == (GO_VENDOR,) and len(relative) > 1:
            return "/".join(relative[1:])
        return "/".join((name, *relative))
    return "/".join(directory.parts) or None
