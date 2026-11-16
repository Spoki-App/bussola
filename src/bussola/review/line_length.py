import json
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import cast

DEFAULT_LINE_LENGTH = 120
RUFF_DEFAULT_LINE_LENGTH = 88
MIN_LINE_LENGTH = 20
MAX_LINE_LENGTH = 400

type ReadFile = Callable[[str], bytes | None]

_EDITORCONFIG_SECTION = re.compile(r"^\s*\[(.*)\]\s*$")
_EDITORCONFIG_LENGTH = re.compile(r"^\s*max_line_length\s*=\s*(\d+)\s*(?:[#;].*)?$", re.IGNORECASE)
_YAML_PRINT_WIDTH = re.compile(r"""^["']?printWidth["']?\s*:\s*(\d+)\s*(?:#.*)?$""", re.MULTILINE)


@dataclass(frozen=True)
class LineLength:
    columns: int
    source: str | None


def _editorconfig(text: str) -> object:
    lengths: dict[str, int] = {}
    section = None
    for line in text.splitlines():
        if header := _EDITORCONFIG_SECTION.match(line):
            section = header.group(1).strip()
        elif section is not None and (length := _EDITORCONFIG_LENGTH.match(line)):
            lengths.setdefault(section, int(length.group(1)))
    return lengths.get("*", next(iter(lengths.values()), None))


def _field(value: object, *keys: str) -> object:
    for key in keys:
        value = cast(dict[str, object], value).get(key) if isinstance(value, dict) else None
    return value


def _toml(text: str) -> object:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None


def _ruff(*keys: str) -> Callable[[str], object]:
    def find(text: str) -> object:
        settings = _field(_toml(text), *keys)
        return cast(dict[str, object], settings).get("line-length", RUFF_DEFAULT_LINE_LENGTH) if isinstance(settings, dict) else None

    return find


def _json(text: str) -> object:
    try:
        return json.loads(text)
    except ValueError:
        return None


def _yaml_print_width(text: str) -> object:
    found = _YAML_PRINT_WIDTH.search(text)
    return int(found.group(1)) if found else None


def _prettierrc(text: str) -> object:
    config = _json(text)
    return _field(config, "printWidth") if config is not None else _yaml_print_width(text)


_SOURCES: tuple[tuple[str, str, Callable[[str], object]], ...] = (
    (".editorconfig", ".editorconfig", _editorconfig),
    (".ruff.toml", ".ruff.toml", _ruff()),
    ("ruff.toml", "ruff.toml", _ruff()),
    ("pyproject.toml", "pyproject.toml ruff", _ruff("tool", "ruff")),
    ("pyproject.toml", "pyproject.toml black", lambda text: _field(_toml(text), "tool", "black", "line-length")),
    (".prettierrc", ".prettierrc", _prettierrc),
    (".prettierrc.json", ".prettierrc.json", lambda text: _field(_json(text), "printWidth")),
    (".prettierrc.yaml", ".prettierrc.yaml", _yaml_print_width),
    (".prettierrc.yml", ".prettierrc.yml", _yaml_print_width),
    (".prettierrc.toml", ".prettierrc.toml", lambda text: _field(_toml(text), "printWidth")),
    ("package.json", "package.json prettier", lambda text: _field(_json(text), "prettier", "printWidth")),
)


def _columns(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and MIN_LINE_LENGTH <= value <= MAX_LINE_LENGTH:
        return value
    return None


def resolve_line_length(read: ReadFile) -> LineLength:
    @cache
    def text_of(path: str) -> str | None:
        data = read(path)
        return None if data is None else data.decode(errors="replace")

    for path, source, find in _SOURCES:
        text = text_of(path)
        columns = _columns(find(text)) if text is not None else None
        if columns is not None:
            return LineLength(columns, source)
    return LineLength(DEFAULT_LINE_LENGTH, None)
