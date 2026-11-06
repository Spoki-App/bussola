import json
from pathlib import Path

import pytest

from bussola.navigation.definitions import Definition, from_hover
from bussola.navigation.docs_links import symbol_docs_url
from bussola.navigation.external import Imported, is_library_file, package_info
from tests.navigation.test_external import LAYOUT

SHORTCUTS = '''import x


def render(
    request, template_name, context=None
) -> "HttpResponse":
    """
    Return an HttpResponse whose content is filled with the result of calling
    django.template.loader.render_to_string().
    """
    pass
'''
APPLICATIONS = '''class FastAPI(Starlette):
    """The main application."""

    def get(self, path: str) -> Callable:
        """Add a GET path operation."""
'''
REACT_TYPES = """export type FC = unknown

/**
 * Returns a stateful value, and a function to update it.
 *
 * @see https://react.dev/reference/react/useState
 */
export function useState<S>(initial: S): [S, (value: S) => void];
"""
TOML_DECODE = """package toml

// Decode decodes the contents of data in TOML format
// into a pointer v.
func Decode(data string, v any) (MetaData, error) {
\treturn nil
}
"""


def site_packages(root: Path) -> Path:
    site = root / ".venv" / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    return site


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_python_standard_library_links_to_the_page_of_the_symbol(tmp_path: Path) -> None:
    join = package_info(Imported("python", "os", "path.join"), tmp_path, ".", LAYOUT)
    loads = package_info(Imported("python", "json", "loads"), tmp_path, ".", LAYOUT)

    assert (join.name, join.version, join.url) == ("os", None, "https://docs.python.org/3/library/os.path.html#os.path.join")
    assert loads.url == "https://docs.python.org/3/library/json.html#json.loads"


def test_a_python_function_gets_its_page_signature_and_docstring_not_only_the_package_home(tmp_path: Path) -> None:
    site = site_packages(tmp_path)
    write(site / "django" / "__init__.py", "")
    shortcuts = write(site / "django" / "shortcuts.py", SHORTCUTS)
    metadata = "Metadata-Version: 2.1\nName: Django\nVersion: 5.1.3\nProject-URL: Documentation, https://docs.djangoproject.com/\n"
    write(site / "Django-5.1.3.dist-info" / "METADATA", metadata)
    write(site / "Django-5.1.3.dist-info" / "top_level.txt", "django\n")

    info = package_info(Imported("python", "django.shortcuts", "render"), tmp_path, ".", LAYOUT)

    assert (info.name, info.version) == ("Django", "5.1.3")
    assert info.url == "https://docs.djangoproject.com/en/5.1/topics/http/shortcuts/#django.shortcuts.render"
    assert info.home_url == "https://docs.djangoproject.com/"
    assert info.definition == Definition(
        shortcuts,
        4,
        'def render(\n    request, template_name, context=None\n) -> "HttpResponse"',
        "Return an HttpResponse whose content is filled with the result of calling\ndjango.template.loader.render_to_string().",
    )
    assert is_library_file(shortcuts, tmp_path)


def test_python_definitions_follow_package_reexports_down_to_methods(tmp_path: Path) -> None:
    site = site_packages(tmp_path)
    write(site / "fastapi" / "__init__.py", '"""FastAPI framework."""\n\nfrom .applications import FastAPI as FastAPI\n')
    applications = write(site / "fastapi" / "applications.py", APPLICATIONS)

    app = package_info(Imported("python", "fastapi", "FastAPI"), tmp_path, ".", LAYOUT)
    get = package_info(Imported("python", "fastapi", "FastAPI.get"), tmp_path, ".", LAYOUT)

    assert app.url == "https://fastapi.tiangolo.com/reference/fastapi/#fastapi.FastAPI"
    assert app.definition == Definition(applications, 1, "class FastAPI(Starlette)", "The main application.")
    assert get.url == "https://fastapi.tiangolo.com/reference/fastapi/#fastapi.FastAPI.get"
    assert get.definition == Definition(applications, 4, "def get(self, path: str) -> Callable", "Add a GET path operation.")


def test_python_definitions_follow_imports_made_only_for_type_checkers(tmp_path: Path) -> None:
    site = site_packages(tmp_path)
    write(site / "pydantic" / "__init__.py", "import typing\n\nif typing.TYPE_CHECKING:\n    from .main import BaseModel\n")
    main = write(site / "pydantic" / "main.py", 'class BaseModel:\n    """Usage docs: models."""\n')

    info = package_info(Imported("python", "pydantic", "BaseModel"), tmp_path, ".", LAYOUT)

    assert info.definition == Definition(main, 1, "class BaseModel", "Usage docs: models.")


def test_a_symbol_without_docstring_still_has_its_signature(tmp_path: Path) -> None:
    module = write(site_packages(tmp_path) / "tinylib" / "__init__.py", "def helper(value: int) -> int:\n    return value\n")

    info = package_info(Imported("python", "tinylib", "helper"), tmp_path, ".", LAYOUT)

    assert info.definition == Definition(module, 1, "def helper(value: int) -> int", None)


def test_python_packages_without_a_symbol_page_keep_the_package_page_apart(tmp_path: Path) -> None:
    missing = package_info(Imported("python", "attrs", "define"), tmp_path, ".", LAYOUT)
    requests = package_info(Imported("python", "requests", "get"), tmp_path, ".", LAYOUT)

    assert (missing.name, missing.url, missing.home_url, missing.definition) == ("attrs", None, "https://pypi.org/project/attrs/", None)
    assert (requests.url, requests.home_url) == ("https://requests.readthedocs.io/en/latest/api/#requests.get", "https://pypi.org/project/requests/")


def test_node_packages_come_from_the_nearest_node_modules_with_their_doc_comment(tmp_path: Path) -> None:
    modules = tmp_path / "frontend" / "node_modules"
    write(modules / "react" / "package.json", json.dumps({"version": "19.1.0", "homepage": "https://react.dev/", "main": "index.js"}))
    write(modules / "react" / "index.js", "module.exports = require('./cjs/react.js')\n")
    types = write(modules / "@types" / "react" / "index.d.ts", REACT_TYPES)

    info = package_info(Imported("ecmascript", "react", "useState"), tmp_path, "frontend/src", LAYOUT)

    assert (info.name, info.version, info.url, info.home_url) == ("react", "19.1.0", "https://react.dev/reference/react/useState", "https://react.dev/")
    assert info.definition == Definition(
        types,
        8,
        "function useState<S>(initial: S): [S, (value: S) => void]",
        "Returns a stateful value, and a function to update it.\n\n@see https://react.dev/reference/react/useState",
    )
    assert is_library_file(types, tmp_path)


def test_node_definitions_follow_relative_reexports(tmp_path: Path) -> None:
    package = tmp_path / "node_modules" / "@tanstack" / "react-query"
    write(package / "package.json", json.dumps({"version": "5.0.0", "types": "build/index.d.ts"}))
    write(package / "build" / "index.d.ts", "export * from './types';\nexport { useQuery } from './useQuery.js';\n")
    use_query = write(
        package / "build" / "useQuery.d.ts", "/** Subscribe to a query. */\ndeclare function useQuery(options: Options): Result;\nexport { useQuery };\n"
    )

    info = package_info(Imported("ecmascript", "@tanstack/react-query", "useQuery"), tmp_path, ".", LAYOUT)

    assert (info.url, info.home_url) == (None, "https://www.npmjs.com/package/@tanstack/react-query")
    assert info.definition == Definition(use_query, 2, "function useQuery(options: Options): Result", "Subscribe to a query.")


def test_node_builtins_link_to_the_function_and_missing_packages_only_to_npm(tmp_path: Path) -> None:
    builtin = package_info(Imported("ecmascript", "node:path", "join"), tmp_path, ".", LAYOUT)
    missing = package_info(Imported("ecmascript", "left-pad", "leftPad"), tmp_path, ".", LAYOUT)

    assert (builtin.name, builtin.url, builtin.home_url) == ("path", "https://nodejs.org/api/path.html#:~:text=path.join", "https://nodejs.org/api/path.html")
    assert (missing.name, missing.url, missing.home_url, missing.definition) == ("left-pad", None, "https://www.npmjs.com/package/left-pad", None)


def test_installed_packages_are_read_again_after_an_upgrade(tmp_path: Path) -> None:
    package = tmp_path / "node_modules" / "left-pad"
    write(package / "package.json", json.dumps({"version": "1.0.0", "main": "index.js"}))
    index = write(package / "index.js", "function leftPad() {}\n")
    before = package_info(Imported("ecmascript", "left-pad", "leftPad"), tmp_path, ".", LAYOUT)

    write(package / "package.json", json.dumps({"version": "1.1.0", "main": "index.js"}))
    write(index, "const version = 2\n\n/** Pads the start. */\nfunction leftPad() {}\n")
    after = package_info(Imported("ecmascript", "left-pad", "leftPad"), tmp_path, ".", LAYOUT)

    assert (before.version, before.definition) == ("1.0.0", Definition(index, 1, "function leftPad()", None))
    assert (after.version, after.definition) == ("1.1.0", Definition(index, 4, "function leftPad()", "Pads the start."))


def test_go_modules_take_their_version_from_go_mod_and_doc_comment_from_the_module_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOMODCACHE", str(tmp_path / "mod"))
    decode = write(tmp_path / "mod" / "github.com" / "!burnt!sushi" / "toml@v1.3.2" / "decode.go", TOML_DECODE)

    info = package_info(Imported("go", "github.com/BurntSushi/toml", "Decode"), tmp_path, ".", LAYOUT)

    assert (info.name, info.version) == ("github.com/BurntSushi/toml", "v1.3.2")
    assert (info.url, info.home_url) == ("https://pkg.go.dev/github.com/BurntSushi/toml#Decode", "https://pkg.go.dev/github.com/BurntSushi/toml")
    assert info.definition == Definition(
        decode, 5, "func Decode(data string, v any) (MetaData, error)", "Decode decodes the contents of data in TOML format\ninto a pointer v."
    )
    assert is_library_file(decode, tmp_path)


def test_go_standard_library_comes_from_goroot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOROOT", str(tmp_path / "go"))
    package = tmp_path / "go" / "src" / "net" / "http"
    request = write(package / "request.go", "package http\n\n// A Request represents an HTTP request.\ntype Request struct {\n\tMethod string\n}\n")
    write(package / "request_test.go", "package http\n\ntype Request struct{}\n")

    info = package_info(Imported("go", "net/http", "Request"), tmp_path, ".", LAYOUT)

    assert (info.name, info.url) == ("net/http", "https://pkg.go.dev/net/http#Request")
    assert info.definition == Definition(request, 4, "type Request struct", "A Request represents an HTTP request.")


@pytest.mark.parametrize(
    ("imported", "version", "docs_base", "url"),
    [
        (
            Imported("python", "django.db", "models.CharField"),
            "4.2.1",
            None,
            "https://docs.djangoproject.com/en/4.2/ref/models/fields/#django.db.models.CharField",
        ),
        (
            Imported("python", "django.db.models", "Model.save"),
            None,
            None,
            "https://docs.djangoproject.com/en/stable/ref/models/instances/#django.db.models.Model.save",
        ),
        (Imported("python", "django.utils.timezone", "now"), "5.1", None, "https://docs.djangoproject.com/en/5.1/search/?q=django.utils.timezone.now"),
        (Imported("python", "fastapi", "Depends"), None, None, "https://fastapi.tiangolo.com/reference/dependencies/#fastapi.Depends"),
        (Imported("python", "flask", "render_template"), None, None, "https://flask.palletsprojects.com/en/stable/api/#flask.render_template"),
        (Imported("python", "numpy", "linalg.norm"), None, None, "https://numpy.org/doc/stable/reference/generated/numpy.linalg.norm.html"),
        (Imported("python", "numpy", "pi"), None, None, None),
        (Imported("python", "pandas", "DataFrame.merge"), None, None, "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html"),
        (Imported("python", "attr", "define"), None, "https://www.attrs.org/", None),
        (Imported("python", "click", "command"), None, "https://click.readthedocs.io/", "https://click.readthedocs.io/en/latest/search.html?q=click.command"),
        (
            Imported("python", "click", "command"),
            None,
            "https://click.readthedocs.io/en/8.1.x/",
            "https://click.readthedocs.io/en/8.1.x/search.html?q=click.command",
        ),
        (Imported("python", "collections.abc", "Mapping"), None, None, "https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping"),
        (
            Imported("python", "xml.etree.ElementTree", "parse"),
            None,
            None,
            "https://docs.python.org/3/library/xml.etree.elementtree.html#xml.etree.ElementTree.parse",
        ),
        (Imported("python", "json.decoder", "JSONDecodeError"), None, None, "https://docs.python.org/3/library/json.html#json.decoder.JSONDecodeError"),
        (Imported("ecmascript", "react", "FC"), None, None, None),
        (Imported("ecmascript", "react", "Suspense"), None, None, "https://react.dev/reference/react/Suspense"),
        (Imported("ecmascript", "react-dom/client", "createRoot"), None, None, "https://react.dev/reference/react-dom/client/createRoot"),
        (Imported("ecmascript", "lodash", "debounce"), None, None, "https://lodash.com/docs/#debounce"),
        (Imported("ecmascript", "lodash/debounce", ""), None, None, "https://lodash.com/docs/#debounce"),
        (Imported("ecmascript", "express", "json"), None, None, "https://expressjs.com/en/api.html#express.json"),
        (Imported("ecmascript", "events", "EventEmitter"), None, None, "https://nodejs.org/api/events.html#:~:text=EventEmitter"),
        (Imported("go", "net/http", "Request.Clone"), None, None, "https://pkg.go.dev/net/http#Request.Clone"),
    ],
)
def test_docs_links_point_at_the_symbol(imported: Imported, version: str | None, docs_base: str | None, url: str | None) -> None:
    assert symbol_docs_url(imported.family, imported.module, imported.name, version, docs_base) == url


@pytest.mark.parametrize(
    ("hover", "expected"),
    [
        (
            "```python\n(function) def render(request) -> HttpResponse\n```\n---\nReturn an HttpResponse.",
            ("(function) def render(request) -> HttpResponse", "python", "Return an HttpResponse."),
        ),
        (
            "```go\nfunc fmt.Println(a ...any) (n int, err error)\n```\n\nPrintln formats.",
            ("func fmt.Println(a ...any) (n int, err error)", "go", "Println formats."),
        ),
        ("```typescript\nfunction useState<S>(): S\n```", ("function useState<S>(): S", "typescript", None)),
        ("Just some text", (None, None, "Just some text")),
        ("```python\n(import) on_commit: Unknown\n```", (None, None, None)),
        ("```typescript\n(alias) const useQuery: any\nimport useQuery\n```", (None, None, None)),
    ],
)
def test_language_server_hover_is_split_into_signature_and_docstring(hover: str, expected: tuple[str | None, str | None, str | None]) -> None:
    found = from_hover(hover)

    assert (found.signature, found.language, found.docstring) == expected
