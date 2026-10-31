import plistlib
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from bussola.handler.registration import (
    LSREGISTER,
    CreateDirectory,
    DeleteRegistryTree,
    ForgetMimeDefault,
    HandlerError,
    MovePath,
    RemovePath,
    RunCommand,
    SetRegistryValue,
    UpdatePlist,
    WriteFile,
    app_properties,
    applescript,
    apply,
    desktop_entry,
    handler_command,
    registration_for,
)

PYTHON = "/opt/tools/bussola/bin/python"
COMMAND = (PYTHON, "-m", "bussola", "open-link")
HANDLER = (*COMMAND, "--")


class Recorder:
    def __init__(self, failing: tuple[str, ...] = ()) -> None:
        self.commands: list[tuple[str, ...]] = []
        self.failing = failing

    def __call__(self, argv: Sequence[str]) -> None:
        self.commands.append(tuple(argv))
        if argv[0] in self.failing:
            raise subprocess.CalledProcessError(1, list(argv), stderr="no such scheme\n")


def test_linux_registers_a_desktop_file_as_default_for_the_scheme(tmp_path: Path) -> None:
    handler = registration_for("linux", tmp_path, {}, PYTHON)
    desktop = tmp_path / ".local/share/applications/bussola-url-handler.desktop"
    recorder = Recorder()

    apply(handler.install, recorder)

    assert handler.location == str(desktop)
    assert desktop.read_text() == desktop_entry(HANDLER)
    assert "MimeType=x-scheme-handler/bussola;\n" in desktop.read_text()
    assert f"Exec={PYTHON} -m bussola open-link -- %u\n" in desktop.read_text()
    assert recorder.commands == [
        ("xdg-mime", "--version"),
        ("xdg-mime", "default", "bussola-url-handler.desktop", "x-scheme-handler/bussola"),
        ("update-desktop-database", str(desktop.parent)),
    ]

    apply(handler.uninstall, recorder)

    assert not desktop.exists()


def test_linux_uninstall_forgets_the_default_xdg_mime_wrote(tmp_path: Path) -> None:
    mimeapps = tmp_path / ".config/mimeapps.list"
    mimeapps.parent.mkdir(parents=True)
    lines = [
        "[Default Applications]",
        "x-scheme-handler/bussola=bussola-url-handler.desktop",
        "text/html=firefox.desktop",
        "[Added Associations]",
        "x-scheme-handler/bussola=other.desktop;bussola-url-handler.desktop;",
    ]
    mimeapps.write_text("\n".join(lines) + "\n")

    apply(registration_for("linux", tmp_path, {}, PYTHON).uninstall, Recorder())

    assert mimeapps.read_text() == "[Default Applications]\ntext/html=firefox.desktop\n[Added Associations]\nx-scheme-handler/bussola=other.desktop;\n"


def test_linux_uninstall_keeps_line_endings_of_mimeapps_list(tmp_path: Path) -> None:
    mimeapps = tmp_path / ".config/mimeapps.list"
    mimeapps.parent.mkdir(parents=True)
    mimeapps.write_bytes(b"[Default Applications]\r\nx-scheme-handler/bussola=other.desktop;bussola-url-handler.desktop;")

    apply(registration_for("linux", tmp_path, {}, PYTHON).uninstall, Recorder())

    assert mimeapps.read_bytes() == b"[Default Applications]\r\nx-scheme-handler/bussola=other.desktop;"


def test_linux_uninstall_also_cleans_the_older_mimeapps_list_location(tmp_path: Path) -> None:
    legacy = tmp_path / ".local/share/applications/mimeapps.list"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("[Default Applications]\nx-scheme-handler/bussola=bussola-url-handler.desktop\n")

    apply(registration_for("linux", tmp_path, {}, PYTHON).uninstall, Recorder())

    assert legacy.read_text() == "[Default Applications]\n"


def test_relative_data_dir_is_recorded_as_an_absolute_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    handler = registration_for("linux", tmp_path, {"BUSSOLA_DATA_DIR": "data"}, PYTHON)
    install = next(step for step in handler.install if isinstance(step, WriteFile))

    assert f"--data-dir {tmp_path.resolve() / 'data'} -- %u" in install.content


def test_linux_uninstall_without_mimeapps_list_creates_none(tmp_path: Path) -> None:
    apply(registration_for("linux", tmp_path, {}, PYTHON).uninstall, Recorder())

    assert not (tmp_path / ".config").exists()


def test_linux_handler_keeps_the_path_of_the_install(tmp_path: Path) -> None:
    handler = registration_for("linux", tmp_path, {"PATH": "/home/me/.local/bin:/usr/bin"}, PYTHON)
    install = next(step for step in handler.install if isinstance(step, WriteFile))

    assert f"Exec=env PATH=/home/me/.local/bin:/usr/bin {PYTHON} -m bussola open-link -- %u\n" in install.content


def test_linux_follows_xdg_data_and_config_home(tmp_path: Path) -> None:
    environ = {"XDG_DATA_HOME": str(tmp_path / "data"), "XDG_CONFIG_HOME": str(tmp_path / "config")}
    handler = registration_for("linux", tmp_path / "home", environ, PYTHON)

    assert handler.location == str(tmp_path / "data/applications/bussola-url-handler.desktop")
    assert ForgetMimeDefault(tmp_path / "config/mimeapps.list") in handler.uninstall


def test_desktop_entry_quotes_arguments_with_reserved_characters() -> None:
    entry = desktop_entry(['/home/me/my tools/py"thon$', "-m", "bussola", "open-link", "50%"])

    assert 'Exec="/home/me/my tools/py\\\\"thon\\\\$" -m bussola open-link 50%% %u\n' in entry


def test_desktop_entry_refuses_line_breaks() -> None:
    with pytest.raises(HandlerError):
        desktop_entry(["/bin/py\nthon"])


def test_macos_builds_an_app_bundle_declaring_the_scheme(tmp_path: Path) -> None:
    handler = registration_for("darwin", tmp_path, {}, PYTHON)
    app = tmp_path / "Applications/bussola.app"
    staged = tmp_path / "Applications/.bussola-new.app"

    assert handler.location == str(app)
    assert handler.install == (
        RemovePath(staged),
        CreateDirectory(tmp_path / "Applications"),
        RunCommand(("osacompile", "-o", str(staged), *[part for line in applescript(HANDLER) for part in ("-e", line)])),
        UpdatePlist(staged / "Contents/Info.plist", app_properties()),
        RunCommand(("codesign", "--force", "--sign", "-", str(staged))),
        RemovePath(app),
        MovePath(staged, app),
        RunCommand((LSREGISTER, "-f", str(app))),
    )
    assert handler.uninstall == (RunCommand((LSREGISTER, "-u", str(app)), required=False), RemovePath(app))


def test_macos_app_bundle_info_plist_after_install(tmp_path: Path) -> None:
    handler = registration_for("darwin", tmp_path, {}, PYTHON)
    plist = tmp_path / "Applications/bussola.app/Contents/Info.plist"

    def fake_osacompile(argv: Sequence[str]) -> None:
        if argv[0] == "osacompile":
            staged_plist = Path(argv[2]) / "Contents/Info.plist"
            staged_plist.parent.mkdir(parents=True)
            staged_plist.write_bytes(plistlib.dumps({"CFBundleExecutable": "applet", "CFBundleIdentifier": "com.apple.ScriptEditor.id.bussola"}))

    apply(handler.install, fake_osacompile)

    properties = plistlib.loads(plist.read_bytes())
    assert properties["CFBundleExecutable"] == "applet"
    assert properties["CFBundleIdentifier"] == "io.github.spoki-app.bussola"
    assert properties["CFBundleURLTypes"] == [{"CFBundleURLName": "bussola link", "CFBundleURLSchemes": ["bussola"]}]
    assert properties["LSUIElement"] is True

    apply(handler.uninstall, lambda _argv: None)

    assert not plist.parent.parent.exists()


def test_a_failed_macos_reinstall_keeps_the_working_app(tmp_path: Path) -> None:
    handler = registration_for("darwin", tmp_path, {}, PYTHON)
    working = tmp_path / "Applications/bussola.app/Contents/Info.plist"
    working.parent.mkdir(parents=True)
    working.write_bytes(plistlib.dumps({"CFBundleExecutable": "applet"}))

    with pytest.raises(HandlerError, match="osacompile failed"):
        apply(handler.install, Recorder(failing=("osacompile",)))

    assert working.is_file()


def test_file_errors_are_reported_as_handler_errors(tmp_path: Path) -> None:
    (tmp_path / "applications").write_text("a file, not a folder")

    with pytest.raises(HandlerError, match="Could not update the registration"):
        apply((WriteFile(tmp_path / "applications/bussola-url-handler.desktop", "x"),), Recorder())


def test_applescript_passes_the_link_as_one_quoted_argument() -> None:
    script = applescript(("/Users/me/my tools/python", "-m", "bussola", "open-link"))

    assert script == [
        "on run",
        'do shell script "\'/Users/me/my tools/python\' -m bussola open-link " & quoted form of "bussola://" & " > /dev/null 2>&1 &"',
        "end run",
        "on open location linkURL",
        'do shell script "\'/Users/me/my tools/python\' -m bussola open-link " & quoted form of linkURL & " > /dev/null 2>&1 &"',
        "end open location",
    ]


def test_macos_handler_keeps_the_path_of_the_install(tmp_path: Path) -> None:
    handler = registration_for("darwin", tmp_path, {"PATH": "/opt/homebrew/bin:/usr/bin"}, PYTHON)
    script = applescript(HANDLER, "/opt/homebrew/bin:/usr/bin")

    assert any(isinstance(step, RunCommand) and step.argv[0] == "osacompile" and script[1] in step.argv for step in handler.install)
    assert script[1].startswith(f'do shell script "PATH=/opt/homebrew/bin:/usr/bin {PYTHON} -m bussola open-link -- "')


def test_windows_writes_the_url_protocol_keys_under_hkcu(tmp_path: Path) -> None:
    python = tmp_path / "Python 3.13" / "python.exe"
    python.parent.mkdir()
    python.touch()
    (python.parent / "pythonw.exe").touch()
    handler = registration_for("win32", tmp_path, {}, str(python))
    windowless = python.parent / "pythonw.exe"

    assert handler.location == "HKCU\\Software\\Classes\\bussola"
    assert handler.install == (
        SetRegistryValue("Software\\Classes\\bussola", "", "URL:bussola link"),
        SetRegistryValue("Software\\Classes\\bussola", "URL Protocol", ""),
        SetRegistryValue("Software\\Classes\\bussola\\shell\\open\\command", "", f'"{windowless}" -m bussola open-link -- "%1"'),
    )
    assert handler.uninstall == (DeleteRegistryTree("Software\\Classes\\bussola"),)


class FakeRegistry:
    def __init__(self, denied: bool = False) -> None:
        self.values: dict[tuple[str, str], str] = {}
        self.denied = denied

    def set_value(self, key: str, name: str, value: str) -> None:
        self.values[key, name] = value

    def delete_tree(self, key: str) -> None:
        if self.denied:
            raise PermissionError("Access is denied")
        self.values = {entry: value for entry, value in self.values.items() if not (entry[0] == key or entry[0].startswith(f"{key}\\"))}


def test_windows_install_and_uninstall_through_the_registry(tmp_path: Path) -> None:
    handler = registration_for("win32", tmp_path, {}, "C:/Python/python.exe")
    registry = FakeRegistry()

    apply(handler.install, Recorder(), registry)
    assert registry.values[("Software\\Classes\\bussola\\shell\\open\\command", "")] == 'C:/Python/python.exe -m bussola open-link -- "%1"'

    apply(handler.uninstall, Recorder(), registry)
    assert registry.values == {}


def test_windows_uninstall_reports_a_key_it_cannot_delete(tmp_path: Path) -> None:
    handler = registration_for("win32", tmp_path, {}, "C:/Python/python.exe")

    with pytest.raises(HandlerError, match="Access is denied"):
        apply(handler.uninstall, Recorder(), FakeRegistry(denied=True))


def test_registry_steps_refuse_to_run_outside_windows(tmp_path: Path) -> None:
    handler = registration_for("win32", tmp_path, {}, "C:/Python/python.exe")

    if sys.platform != "win32":
        with pytest.raises(HandlerError, match="only on Windows"):
            apply(handler.install, Recorder())


def test_handler_keeps_the_data_dir_it_was_installed_with(tmp_path: Path) -> None:
    handler = registration_for("linux", tmp_path, {"BUSSOLA_DATA_DIR": "/srv/bussola data"}, PYTHON)
    install = next(step for step in handler.install if isinstance(step, WriteFile))

    assert f'Exec={PYTHON} -m bussola open-link --data-dir "/srv/bussola data" -- %u\n' in install.content


def test_every_handler_ends_options_before_the_link(tmp_path: Path) -> None:
    environ = {"BUSSOLA_DATA_DIR": "/srv/data"}
    linux = next(step for step in registration_for("linux", tmp_path, environ, PYTHON).install if isinstance(step, WriteFile))
    windows = registration_for("win32", tmp_path, environ, PYTHON).install[-1]

    assert "open-link --data-dir /srv/data -- %u\n" in linux.content
    assert (
        'open-link --data-dir /srv/data -- " & quoted form of linkURL'
        in applescript((PYTHON, "-m", "bussola", "open-link", "--data-dir", "/srv/data", "--"))[4]
    )
    assert isinstance(windows, SetRegistryValue)
    assert windows.value.endswith('open-link --data-dir /srv/data -- "%1"')


def test_handler_command_uses_the_current_python() -> None:
    assert handler_command("linux", PYTHON) == COMMAND
    assert handler_command("win32", "C:/missing/python.exe") == ("C:/missing/python.exe", "-m", "bussola", "open-link")


def test_unsupported_platform_is_refused(tmp_path: Path) -> None:
    with pytest.raises(HandlerError):
        registration_for("aix", tmp_path, {}, PYTHON)


def test_a_failing_required_command_stops_the_install_with_its_error(tmp_path: Path) -> None:
    handler = registration_for("linux", tmp_path, {}, PYTHON)

    with pytest.raises(HandlerError, match="xdg-mime failed: no such scheme"):
        apply(handler.install, Recorder(failing=("xdg-mime",)))

    assert not (tmp_path / ".local/share/applications/bussola-url-handler.desktop").exists()


def test_optional_commands_may_fail_or_be_missing(tmp_path: Path) -> None:
    def missing(argv: Sequence[str]) -> None:
        raise FileNotFoundError(argv[0])

    apply((RunCommand(("update-desktop-database",), required=False), WriteFile(tmp_path / "a", "x")), missing)

    assert (tmp_path / "a").read_text() == "x"
    with pytest.raises(HandlerError, match="Could not run xdg-mime"):
        apply((RunCommand(("xdg-mime",)),), missing)
