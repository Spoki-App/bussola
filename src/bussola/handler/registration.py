import importlib
import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

from bussola.errors import DomainError
from bussola.handler.links import BUSSOLA_MODULE, SCHEME
from bussola.storage.database import DATA_DIR_ENV

WINREG: ModuleType | None = importlib.import_module("winreg") if sys.platform == "win32" else None

DISPLAY_NAME = "bussola"
BUNDLE_ID = "io.github.spoki-app.bussola"
URL_NAME = f"{DISPLAY_NAME} link"
DESKTOP_FILE = "bussola-url-handler.desktop"
MIME_TYPE = f"x-scheme-handler/{SCHEME}"
MIMEAPPS_FILE = "mimeapps.list"
MAC_APP = f"{DISPLAY_NAME}.app"
MAC_STAGED_APP = f".{DISPLAY_NAME}-new.app"
LSREGISTER = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
WINDOWS_CLASSES_KEY = rf"Software\Classes\{SCHEME}"
WINDOWS_COMMAND_KEY = rf"{WINDOWS_CLASSES_KEY}\shell\open\command"
WINDOWS_GUI_PYTHON = "pythonw.exe"
DESKTOP_RESERVED = re.compile(r"[\s\"'\\><~|&;$*?#()`]")
DESKTOP_ESCAPED = re.compile(r"([\"`$\\])")
HANDLER_ARGUMENTS = (*BUSSOLA_MODULE, "open-link")
END_OF_OPTIONS = "--"


class HandlerError(DomainError):
    pass


@dataclass(frozen=True)
class CreateDirectory:
    path: Path


@dataclass(frozen=True)
class WriteFile:
    path: Path
    content: str


@dataclass(frozen=True)
class RemovePath:
    path: Path


@dataclass(frozen=True)
class MovePath:
    source: Path
    target: Path


@dataclass(frozen=True)
class UpdatePlist:
    path: Path
    values: Mapping[str, Any]


@dataclass(frozen=True)
class ForgetMimeDefault:
    path: Path


@dataclass(frozen=True)
class SetRegistryValue:
    key: str
    name: str
    value: str


@dataclass(frozen=True)
class DeleteRegistryTree:
    key: str


@dataclass(frozen=True)
class RunCommand:
    argv: tuple[str, ...]
    required: bool = True


type Step = CreateDirectory | WriteFile | RemovePath | MovePath | UpdatePlist | ForgetMimeDefault | SetRegistryValue | DeleteRegistryTree | RunCommand
type Runner = Callable[[Sequence[str]], object]


class Registry(Protocol):
    def set_value(self, key: str, name: str, value: str) -> None: ...

    def delete_tree(self, key: str) -> None: ...


class CurrentUserRegistry:
    def set_value(self, key: str, name: str, value: str) -> None:
        registry = _windows_registry()
        with registry.CreateKey(registry.HKEY_CURRENT_USER, key) as handle:
            registry.SetValueEx(handle, name, 0, registry.REG_SZ, value)

    def delete_tree(self, key: str) -> None:
        registry = _windows_registry()
        try:
            with registry.OpenKey(registry.HKEY_CURRENT_USER, key) as handle:
                children = [registry.EnumKey(handle, index) for index in range(registry.QueryInfoKey(handle)[0])]
        except FileNotFoundError:
            return
        for child in children:
            self.delete_tree(rf"{key}\{child}")
        registry.DeleteKey(registry.HKEY_CURRENT_USER, key)


def _windows_registry() -> ModuleType:
    if WINREG is None:
        raise HandlerError("The registry exists only on Windows")
    return WINREG


@dataclass(frozen=True)
class Registration:
    location: str
    install: tuple[Step, ...]
    uninstall: tuple[Step, ...]


def current_registration() -> Registration:
    return registration_for(sys.platform, Path.home(), os.environ, sys.executable)


def registration_for(system: str, home: Path, environ: Mapping[str, str], executable: str) -> Registration:
    data_dir = environ.get(DATA_DIR_ENV)
    search_path = environ.get("PATH") if system != "win32" else None
    options = (
        *(("--data-dir", str(Path(data_dir).resolve())) if data_dir else ()),
        *(("--search-path", search_path) if search_path else ()),
    )
    command = (*handler_command(system, executable), *options, END_OF_OPTIONS)
    if system.startswith("linux"):
        applications_dir = xdg_applications_dir(home, environ)
        return linux_registration(command, applications_dir, (xdg_mimeapps_file(home, environ), applications_dir / MIMEAPPS_FILE))
    if system == "darwin":
        return macos_registration(command, home / "Applications")
    if system == "win32":
        return windows_registration(command)
    raise HandlerError(f"Registering {SCHEME}:// links is not supported on {system}")


def handler_command(system: str, executable: str) -> tuple[str, ...]:
    python = Path(executable)
    windowless = python.with_name(WINDOWS_GUI_PYTHON)
    if system == "win32" and windowless.is_file():
        python = windowless
    return (str(python), *HANDLER_ARGUMENTS)


def xdg_applications_dir(home: Path, environ: Mapping[str, str]) -> Path:
    return _xdg_dir(environ, "XDG_DATA_HOME", home / ".local" / "share") / "applications"


def xdg_mimeapps_file(home: Path, environ: Mapping[str, str]) -> Path:
    return _xdg_dir(environ, "XDG_CONFIG_HOME", home / ".config") / MIMEAPPS_FILE


def _xdg_dir(environ: Mapping[str, str], variable: str, default: Path) -> Path:
    value = Path(environ.get(variable, ""))
    return value if value.is_absolute() else default


def linux_registration(command: Sequence[str], applications_dir: Path, mimeapps: Sequence[Path]) -> Registration:
    desktop = applications_dir / DESKTOP_FILE
    refresh = RunCommand(("update-desktop-database", str(applications_dir)), required=False)
    return Registration(
        location=str(desktop),
        install=(
            RunCommand(("xdg-mime", "--version")),
            WriteFile(desktop, desktop_entry(command)),
            RunCommand(("xdg-mime", "default", DESKTOP_FILE, MIME_TYPE)),
            refresh,
        ),
        uninstall=(RemovePath(desktop), *(ForgetMimeDefault(path) for path in mimeapps), refresh),
    )


def desktop_entry(command: Sequence[str]) -> str:
    exec_line = " ".join([*(_desktop_argument(argument) for argument in command), "%u"])
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={DISPLAY_NAME}",
        f"Comment=Open {SCHEME}:// links in {DISPLAY_NAME}",
        f"Exec={exec_line}",
        "Terminal=false",
        "NoDisplay=true",
        f"MimeType={MIME_TYPE};",
    ]
    return "\n".join(lines) + "\n"


def macos_registration(command: Sequence[str], applications_dir: Path) -> Registration:
    app = applications_dir / MAC_APP
    staged = applications_dir / MAC_STAGED_APP
    script = [argument for line in applescript(command) for argument in ("-e", line)]
    return Registration(
        location=str(app),
        install=(
            RemovePath(staged),
            CreateDirectory(applications_dir),
            RunCommand(("osacompile", "-o", str(staged), *script)),
            UpdatePlist(staged / "Contents" / "Info.plist", app_properties()),
            RunCommand(("codesign", "--force", "--sign", "-", str(staged))),
            RemovePath(app),
            MovePath(staged, app),
            RunCommand((LSREGISTER, "-f", str(app))),
        ),
        uninstall=(RunCommand((LSREGISTER, "-u", str(app)), required=False), RemovePath(app)),
    )


def applescript(command: Sequence[str]) -> list[str]:
    shell_command = _applescript_string(f"{shlex.join(command)} ")
    background = _applescript_string(" > /dev/null 2>&1 &")
    return [
        "on run",
        f"do shell script {shell_command} & quoted form of {_applescript_string(f'{SCHEME}://')} & {background}",
        "end run",
        "on open location linkURL",
        f"do shell script {shell_command} & quoted form of linkURL & {background}",
        "end open location",
    ]


def app_properties() -> dict[str, Any]:
    return {
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleName": DISPLAY_NAME,
        "CFBundleURLTypes": [{"CFBundleURLName": URL_NAME, "CFBundleURLSchemes": [SCHEME]}],
        "LSUIElement": True,
    }


def windows_registration(command: Sequence[str]) -> Registration:
    command_line = f'{subprocess.list2cmdline(command)} "%1"'
    return Registration(
        location=rf"HKCU\{WINDOWS_CLASSES_KEY}",
        install=(
            SetRegistryValue(WINDOWS_CLASSES_KEY, "", f"URL:{URL_NAME}"),
            SetRegistryValue(WINDOWS_CLASSES_KEY, "URL Protocol", ""),
            SetRegistryValue(WINDOWS_COMMAND_KEY, "", command_line),
        ),
        uninstall=(DeleteRegistryTree(WINDOWS_CLASSES_KEY),),
    )


def run_command(argv: Sequence[str]) -> None:
    subprocess.run(argv, check=True, capture_output=True, text=True)


def apply(steps: Sequence[Step], run: Runner | None = None, registry: Registry | None = None) -> None:
    for step in steps:
        try:
            _apply_step(step, run or run_command, registry or CurrentUserRegistry())
        except (OSError, ValueError) as error:
            raise HandlerError(f"Could not update the registration: {error}") from error


def _apply_step(step: Step, run: Runner, registry: Registry) -> None:
    match step:
        case CreateDirectory(path):
            path.mkdir(parents=True, exist_ok=True)
        case WriteFile(path, content):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        case RemovePath(path):
            _remove(path)
        case MovePath(source, target):
            source.rename(target)
        case UpdatePlist(path, values):
            _update_plist(path, values)
        case ForgetMimeDefault(path):
            _forget_mime_default(path)
        case SetRegistryValue(key, name, value):
            registry.set_value(key, name, value)
        case DeleteRegistryTree(key):
            registry.delete_tree(key)
        case RunCommand(argv, required):
            _run(run, argv, required=required)


def _run(run: Runner, argv: Sequence[str], *, required: bool) -> None:
    try:
        run(argv)
    except (subprocess.CalledProcessError, OSError) as error:
        if not required:
            return
        if isinstance(error, subprocess.CalledProcessError):
            raise HandlerError(f"{argv[0]} failed: {(error.stderr or '').strip() or error}") from error
        raise HandlerError(f"Could not run {argv[0]}: {error}") from error


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _update_plist(path: Path, values: Mapping[str, Any]) -> None:
    with path.open("rb") as file:
        properties = plistlib.load(file)
    properties.update(values)
    with path.open("wb") as file:
        plistlib.dump(properties, file)


def _forget_mime_default(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_bytes().decode("utf-8")
    kept = "".join(line for line in (_without_handler(line) for line in text.splitlines(keepends=True)) if line is not None)
    if kept != text:
        path.write_bytes(kept.encode("utf-8"))


def _without_handler(line: str) -> str | None:
    content = line.rstrip("\r\n")
    ending = line[len(content) :]
    key, separator, value = content.partition("=")
    if not separator or key.strip() != MIME_TYPE:
        return line
    handlers = [handler for handler in value.split(";") if handler.strip() and handler.strip() != DESKTOP_FILE]
    if not handlers:
        return None
    return f"{key}={';'.join(handlers)}{';' if value.endswith(';') else ''}{ending}"


def _desktop_argument(argument: str) -> str:
    if "\n" in argument or "\r" in argument:
        raise HandlerError(f"Cannot register a command with a line break: {argument!r}")
    escaped = argument.replace("%", "%%")
    if DESKTOP_RESERVED.search(escaped) is None:
        return escaped
    quoted = '"' + DESKTOP_ESCAPED.sub(r"\\\1", escaped) + '"'
    return quoted.replace("\\", "\\\\")


def _applescript_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
