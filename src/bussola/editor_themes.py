import hashlib
import json
import os
import plistlib
import re
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from bussola.errors import InvalidRequestError, NotFoundError

MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_INCLUDE_DEPTH = 8
LIGHT_UI_THEMES = frozenset({"vs", "hc-light"})
PACKAGE_FILE = "package.json"
NLS_FILE = "package.nls.json"
JSON_STRING = r'"(?:[^"\\]|\\.)*"'
JSON_COMMENT = r"//[^\n]*|/\*.*?(?:\*/|$)"
TRAILING_COMMA = r",(?=\s*[}\]])"
JSONC_TOKEN = re.compile(rf"({JSON_STRING})|{JSON_COMMENT}", re.DOTALL)
JSONC_COMMA = re.compile(rf"({JSON_STRING})|{TRAILING_COMMA}", re.DOTALL)

type JsonObject = dict[str, object]


@dataclass(frozen=True)
class ThemeSource:
    editor: str
    extensions_dir: Path


@dataclass(frozen=True)
class EditorTheme:
    id: str
    label: str
    editor: str
    extension: str
    type: str
    path: Path
    root: Path


def default_sources() -> list[ThemeSource]:
    home = Path.home()
    sources = [
        ThemeSource("VS Code", home / ".vscode" / "extensions"),
        ThemeSource("VS Code Insiders", home / ".vscode-insiders" / "extensions"),
        ThemeSource("Cursor", home / ".cursor" / "extensions"),
        ThemeSource("Windsurf", home / ".windsurf" / "extensions"),
        ThemeSource("VSCodium", home / ".vscode-oss" / "extensions"),
    ]
    return sources + [ThemeSource(editor, path) for editor, path in _builtin_dirs(home)]


def _builtin_dirs(home: Path) -> Iterator[tuple[str, Path]]:
    if sys.platform == "darwin":
        apps = {
            "VS Code": "Visual Studio Code.app",
            "VS Code Insiders": "Visual Studio Code - Insiders.app",
            "Cursor": "Cursor.app",
            "Windsurf": "Windsurf.app",
            "VSCodium": "VSCodium.app",
        }
        for editor, app in apps.items():
            for applications in (Path("/Applications"), home / "Applications"):
                yield editor, applications / app / "Contents" / "Resources" / "app" / "extensions"
    elif sys.platform == "win32":
        programs = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "Programs"
        apps = {
            "VS Code": "Microsoft VS Code",
            "VS Code Insiders": "Microsoft VS Code Insiders",
            "Cursor": "cursor",
            "Windsurf": "Windsurf",
            "VSCodium": "VSCodium",
        }
        for editor, app in apps.items():
            yield editor, programs / app / "resources" / "app" / "extensions"
    else:
        apps = {"VS Code": ("code", "visual-studio-code"), "VS Code Insiders": ("code-insiders",), "Cursor": ("cursor",), "VSCodium": ("codium", "vscodium")}
        for editor, names in apps.items():
            for name in names:
                for parent in (Path("/usr/share"), Path("/usr/lib"), Path("/opt")):
                    yield editor, parent / name / "resources" / "app" / "extensions"


def strip_jsonc(text: str) -> str:
    without_comments = JSONC_TOKEN.sub(lambda match: match.group(1) or "", text)
    return JSONC_COMMA.sub(lambda match: match.group(1) or "", without_comments)


def _read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


def _object(value: object) -> JsonObject | None:
    return cast(JsonObject, value) if isinstance(value, dict) else None


def _list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _read_json(path: Path) -> object:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return cast(object, json.loads(strip_jsonc(text)))
    except ValueError:
        return None


def _inside(path: Path, root: Path) -> Path | None:
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return None
    return resolved if resolved.is_relative_to(root) and resolved.is_file() else None


def _localized(label: str, nls: JsonObject) -> str:
    if label.startswith("%") and label.endswith("%"):
        value = nls.get(label[1:-1])
        message = _object(value)
        if message is not None:
            value = message.get("message")
        if isinstance(value, str):
            return value
    return label


def _version(package: JsonObject) -> tuple[int, ...]:
    version = package.get("version")
    return tuple(int(part) for part in re.findall(r"\d+", version)) if isinstance(version, str) else ()


def _extension_dirs(source: ThemeSource) -> Iterator[Path]:
    try:
        children = sorted(source.extensions_dir.iterdir())
    except OSError:
        return
    for child in children:
        if not child.name.startswith(".") and child.is_dir():
            yield child


def _latest_packages(source: ThemeSource) -> Iterator[tuple[Path, JsonObject]]:
    latest: dict[str, tuple[tuple[int, ...], Path, JsonObject]] = {}
    for directory in _extension_dirs(source):
        package = _object(_read_json(directory / PACKAGE_FILE))
        if package is None:
            continue
        key = f"{package.get('publisher', '')}.{package.get('name', directory.name)}".lower()
        current = latest.get(key)
        if current is None or _version(package) > current[0]:
            latest[key] = (_version(package), directory, package)
    for _version_key, directory, package in latest.values():
        yield directory, package


def _themes_of(source: ThemeSource, directory: Path, package: JsonObject) -> Iterator[EditorTheme]:
    contributes = _object(package.get("contributes")) or {}
    root = directory.resolve()
    nls = _object(_read_json(directory / NLS_FILE)) or {}
    extension = _localized(str(package.get("displayName") or package.get("name") or directory.name), nls)
    for item in _list(contributes.get("themes")):
        entry = _object(item)
        relative = entry.get("path") if entry else None
        if entry is None or not isinstance(relative, str):
            continue
        path = _inside(directory / relative, root)
        if path is None:
            continue
        label = _localized(str(entry.get("label") or entry.get("id") or path.stem), nls)
        kind = "light" if entry.get("uiTheme") in LIGHT_UI_THEMES else "dark"
        theme_id = hashlib.sha256(f"{source.editor}\n{path}".encode()).hexdigest()[:20]
        yield EditorTheme(theme_id, label, source.editor, extension, kind, path, root)


def find_editor_themes(sources: Sequence[ThemeSource] | None = None) -> list[EditorTheme]:
    found: dict[str, EditorTheme] = {}
    for source in default_sources() if sources is None else sources:
        for directory, package in _latest_packages(source):
            for theme in _themes_of(source, directory, package):
                found.setdefault(theme.id, theme)
    return sorted(found.values(), key=lambda theme: (theme.editor.lower(), theme.label.lower()))


def _token_colors(value: object, base: Path, root: Path) -> list[object]:
    if not isinstance(value, str):
        return _list(value)
    path = _inside(base.parent / value, root)
    if path is None:
        return []
    if path.suffix.lower() in {".tmtheme", ".plist"}:
        try:
            with path.open("rb") as file:
                plist = _object(cast(object, plistlib.load(file)))
        except (OSError, plistlib.InvalidFileException, ValueError):
            return []
        return _list(plist.get("settings")) if plist else []
    data = _read_json(path)
    wrapper = _object(data)
    if wrapper is not None:
        data = wrapper.get("tokenColors", wrapper.get("settings"))
    return _list(data)


def _merged(path: Path, root: Path, seen: Iterable[Path] = ()) -> tuple[JsonObject, list[object]]:
    visited = [*seen, path]
    data = _object(_read_json(path))
    if data is None:
        raise InvalidRequestError(f"{path.name} is not a valid color theme")
    colors: JsonObject = {}
    token_colors: list[object] = []
    include = data.get("include")
    if isinstance(include, str) and len(visited) <= MAX_INCLUDE_DEPTH:
        parent = _inside(path.parent / include, root)
        if parent is not None and parent not in visited:
            colors, token_colors = _merged(parent, root, visited)
    colors = {**colors, **(_object(data.get("colors")) or {})}
    return colors, [*token_colors, *_token_colors(data.get("tokenColors"), path, root)]


def editor_theme_content(theme_id: str, sources: Sequence[ThemeSource] | None = None) -> JsonObject:
    theme = next((theme for theme in find_editor_themes(sources) if theme.id == theme_id), None)
    if theme is None:
        raise NotFoundError("This theme is no longer installed")
    colors, token_colors = _merged(theme.path, theme.root)
    return {
        "name": theme.label,
        "type": theme.type,
        "colors": {key: value for key, value in colors.items() if isinstance(value, str)},
        "tokenColors": [entry for entry in token_colors if isinstance(entry, dict)],
    }
