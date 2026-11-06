import json
import plistlib
from pathlib import Path

import pytest

from bussola.editor_themes import ThemeSource, editor_theme_content, find_editor_themes, strip_jsonc
from bussola.errors import NotFoundError
from tests.apiclient import ApiClient


def write_extension(root: Path, folder: str, package: dict[str, object], files: dict[str, str], nls: dict[str, str] | None = None) -> Path:
    directory = root / folder
    directory.mkdir(parents=True)
    (directory / "package.json").write_text(json.dumps(package))
    if nls is not None:
        (directory / "package.nls.json").write_text(json.dumps(nls))
    for name, text in files.items():
        (directory / name).parent.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(text)
    return directory


def theme_package(name: str, version: str, themes: list[dict[str, str]], display_name: str | None = None) -> dict[str, object]:
    return {"name": name, "publisher": "acme", "version": version, "displayName": display_name or name, "contributes": {"themes": themes}}


NIGHT_JSONC = """{
  // night
  "colors": {"editor.background": "#101010",},
  "tokenColors": [{"scope": "comment", "settings": {"foreground": "#555555"}},],
}"""


@pytest.fixture
def home(tmp_path: Path) -> Path:
    root = tmp_path / "home"
    vscode = root / ".vscode" / "extensions"
    write_extension(
        vscode,
        "acme.night-2.0.0",
        theme_package("night", "2.0.0", [{"label": "Night", "uiTheme": "vs-dark", "path": "./themes/night.json"}], "Night Theme"),
        {"themes/night.json": NIGHT_JSONC},
    )
    write_extension(
        vscode,
        "acme.night-1.9.0",
        theme_package("night", "1.9.0", [{"label": "Night (old)", "uiTheme": "vs-dark", "path": "./themes/night.json"}]),
        {"themes/night.json": '{"colors": {"editor.background": "#000000"}}'},
    )
    write_extension(vscode, ".obsolete-folder", theme_package("hidden", "1.0.0", [{"label": "Hidden", "path": "./h.json"}]), {"h.json": "{}"})
    write_extension(
        vscode,
        "acme.escape-1.0.0",
        theme_package("escape", "1.0.0", [{"label": "Escape", "path": "../../secret.json"}, {"label": "Missing", "path": "./missing.json"}]),
        {},
    )
    write_extension(
        root / ".cursor" / "extensions",
        "acme.paper-1.0.0",
        theme_package("paper", "1.0.0", [{"label": "Paper", "uiTheme": "vs", "path": "./paper.json"}]),
        {"paper.json": '{"type": "light", "colors": {"editor.background": "#fafafa"}}'},
    )
    (root / "secret.json").write_text('{"colors": {"editor.background": "#ff0000"}}')
    return root


@pytest.fixture
def builtin(tmp_path: Path) -> ThemeSource:
    root = tmp_path / "app" / "extensions"
    write_extension(
        root,
        "theme-defaults",
        theme_package("theme-defaults", "1.0.0", [{"label": "%darkPlus%", "uiTheme": "vs-dark", "path": "./themes/dark_plus.json"}], "%displayName%"),
        {
            "themes/dark_vs.json": json.dumps(
                {
                    "colors": {"editor.background": "#1e1e1e", "editor.foreground": "#d4d4d4"},
                    "tokenColors": [{"scope": "keyword", "settings": {"foreground": "#569cd6"}}],
                }
            ),
            "themes/dark_plus.json": json.dumps(
                {
                    "include": "./dark_vs.json",
                    "colors": {"editor.foreground": "#cccccc"},
                    "tokenColors": [{"scope": "entity.name.function", "settings": {"foreground": "#dcdcaa"}}],
                }
            ),
        },
        {"darkPlus": "Dark+", "displayName": "Default Themes"},
    )
    tm_theme = plistlib.dumps({"settings": [{"scope": "string", "settings": {"foreground": "#ce9178"}}]}).decode()
    write_extension(
        root,
        "theme-kimbie",
        theme_package(
            "theme-kimbie",
            "1.0.0",
            [{"label": "Kimbie", "uiTheme": "vs-dark", "path": "./themes/kimbie.json"}, {"label": "Loop", "path": "./themes/loop.json"}],
        ),
        {
            "themes/kimbie.json": json.dumps({"colors": {"editor.background": "#221a0f"}, "tokenColors": "./kimbie.tmTheme"}),
            "themes/kimbie.tmTheme": tm_theme,
            "themes/loop.json": json.dumps({"include": "./loop.json", "colors": {"editor.background": "#123456"}}),
        },
    )
    return ThemeSource("VS Code", root)


def sources(home: Path, builtin: ThemeSource | None = None) -> list[ThemeSource]:
    found = [ThemeSource("VS Code", home / ".vscode" / "extensions"), ThemeSource("Cursor", home / ".cursor" / "extensions")]
    return found if builtin is None else [*found, builtin]


def test_strip_jsonc_keeps_strings_and_drops_comments_and_trailing_commas() -> None:
    text = '{"url": "https://example.com/*x*/", // note\n "list": [1, 2,], /* gone */ "a": {"b": "c,}",},}'

    assert json.loads(strip_jsonc(text)) == {"url": "https://example.com/*x*/", "list": [1, 2], "a": {"b": "c,}"}}


def test_lists_themes_of_the_latest_version_of_each_extension(home: Path) -> None:
    themes = find_editor_themes(sources(home))

    assert [(theme.editor, theme.label, theme.extension, theme.type) for theme in themes] == [
        ("Cursor", "Paper", "paper", "light"),
        ("VS Code", "Night", "Night Theme", "dark"),
    ]


def test_skips_hidden_folders_missing_files_and_paths_outside_the_extension(home: Path) -> None:
    labels = {theme.label for theme in find_editor_themes(sources(home))}

    assert labels.isdisjoint({"Hidden", "Escape", "Missing", "Night (old)"})


def test_reads_jsonc_theme_files(home: Path) -> None:
    night = next(theme for theme in find_editor_themes(sources(home)) if theme.label == "Night")

    content = editor_theme_content(night.id, sources(home))

    assert content == {
        "name": "Night",
        "type": "dark",
        "colors": {"editor.background": "#101010"},
        "tokenColors": [{"scope": "comment", "settings": {"foreground": "#555555"}}],
    }


def test_resolves_localized_labels_and_include_chains(home: Path, builtin: ThemeSource) -> None:
    dark_plus = next(theme for theme in find_editor_themes(sources(home, builtin)) if theme.label == "Dark+")

    content = editor_theme_content(dark_plus.id, sources(home, builtin))

    assert dark_plus.extension == "Default Themes"
    assert content["colors"] == {"editor.background": "#1e1e1e", "editor.foreground": "#cccccc"}
    assert content["tokenColors"] == [
        {"scope": "keyword", "settings": {"foreground": "#569cd6"}},
        {"scope": "entity.name.function", "settings": {"foreground": "#dcdcaa"}},
    ]


def test_reads_token_colors_from_a_tmtheme_file(home: Path, builtin: ThemeSource) -> None:
    kimbie = next(theme for theme in find_editor_themes(sources(home, builtin)) if theme.label == "Kimbie")

    assert editor_theme_content(kimbie.id, sources(home, builtin))["tokenColors"] == [{"scope": "string", "settings": {"foreground": "#ce9178"}}]


def test_stops_at_an_include_cycle(home: Path, builtin: ThemeSource) -> None:
    loop = next(theme for theme in find_editor_themes(sources(home, builtin)) if theme.label == "Loop")

    assert editor_theme_content(loop.id, sources(home, builtin))["colors"] == {"editor.background": "#123456"}


def test_unknown_theme_is_not_found(home: Path) -> None:
    with pytest.raises(NotFoundError):
        editor_theme_content("nope", sources(home))


def test_api_lists_and_reads_installed_themes(api: ApiClient, home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    themes = api.call("GET", "/editor-themes")
    paper = next(theme for theme in themes if theme["label"] == "Paper" and theme["editor"] == "Cursor")
    content = api.call("GET", f"/editor-themes/{paper['id']}")

    assert paper == {"id": paper["id"], "label": "Paper", "editor": "Cursor", "extension": "paper", "type": "light"}
    assert content["colors"] == {"editor.background": "#fafafa"}
    api.call("GET", "/editor-themes/unknown", 404)
