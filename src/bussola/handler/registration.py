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
from typing import Any

from bussola.errors import DomainError
from bussola.handler.links import SCHEME

DISPLAY_NAME = "bussola"
BUNDLE_ID = "io.github.spoki-app.bussola"
URL_NAME = f"{DISPLAY_NAME} link"
DESKTOP_FILE = "bussola-url-handler.desktop"
MIME_TYPE = f"x-scheme-handler/{SCHEME}"
MAC_APP = f"{DISPLAY_NAME}.app"
LSREGISTER = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
WINDOWS_KEY = rf"HKCU\Software\Classes\{SCHEME}"
WINDOWS_COMMAND_KEY = rf"{WINDOWS_KEY}\shell\open\command"
WINDOWS_GUI_PYTHON = "pythonw.exe"
DESKTOP_RESERVED = re.compile(r"[\s\"'\\><~|&;$*?#()`]")
DESKTOP_ESCAPED = re.compile(r"([\"`$\\])")
HANDLER_ARGUMENTS = ("-m", "bussola", "open-link")


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
class UpdatePlist:
    path: Path
    values: Mapping[str, Any]


@dataclass(frozen=True)
class RunCommand:
    argv: tuple[str, ...]
    required: bool = True


type Step = CreateDirectory | WriteFile | RemovePath | UpdatePlist | RunCommand
type Runner = Callable[[Sequence[str]], object]


@dataclass(frozen=True)
class Registration:
    location: str
    install: tuple[Step, ...]
    uninstall: tuple[Step, ...]


def current_registration() -> Registration:
    return registration_for(sys.platform, Path.home(), os.environ, sys.executable)


def registration_for(system: str, home: Path, environ: Mapping[str, str], executable: str) -> Registration:
    command = handler_command(system, executable)
    if system.startswith("linux"):
        return linux_registration(command, xdg_applications_dir(home, environ))
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
    data_home = environ.get("XDG_DATA_HOME", "")
    base = Path(data_home) if Path(data_home).is_absolute() else home / ".local" / "share"
    return base / "applications"


def linux_registration(command: Sequence[str], applications_dir: Path) -> Registration:
    desktop = applications_dir / DESKTOP_FILE
    refresh = RunCommand(("update-desktop-database", str(applications_dir)), required=False)
    return Registration(
        location=str(desktop),
        install=(
            WriteFile(desktop, desktop_entry(command)),
            RunCommand(("xdg-mime", "default", DESKTOP_FILE, MIME_TYPE)),
            refresh,
        ),
        uninstall=(RemovePath(desktop), refresh),
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
    script = [argument for line in applescript(command) for argument in ("-e", line)]
    return Registration(
        location=str(app),
        install=(
            RemovePath(app),
            CreateDirectory(applications_dir),
            RunCommand(("osacompile", "-o", str(app), *script)),
            UpdatePlist(app / "Contents" / "Info.plist", app_properties()),
            RunCommand(("codesign", "--force", "--sign", "-", str(app))),
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
        location=WINDOWS_KEY,
        install=(
            RunCommand(("reg", "add", WINDOWS_KEY, "/ve", "/d", f"URL:{URL_NAME}", "/f")),
            RunCommand(("reg", "add", WINDOWS_KEY, "/v", "URL Protocol", "/d", "", "/f")),
            RunCommand(("reg", "add", WINDOWS_COMMAND_KEY, "/ve", "/d", command_line, "/f")),
        ),
        uninstall=(RunCommand(("reg", "delete", WINDOWS_KEY, "/f"), required=False),),
    )


def run_command(argv: Sequence[str]) -> None:
    subprocess.run(argv, check=True, capture_output=True, text=True)


def apply(steps: Sequence[Step], run: Runner | None = None) -> None:
    for step in steps:
        match step:
            case CreateDirectory(path):
                path.mkdir(parents=True, exist_ok=True)
            case WriteFile(path, content):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            case RemovePath(path):
                _remove(path)
            case UpdatePlist(path, values):
                _update_plist(path, values)
            case RunCommand(argv, required):
                _run(run or run_command, argv, required=required)


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
