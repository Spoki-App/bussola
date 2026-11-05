import json
from pathlib import Path

import pytest

from bussola.navigation.external import Imported, LibrarySource, ProjectLayout, imported_symbol, is_library_file, package_info
from bussola.navigation.symbols import identifier_at, language_for, parse

REPO_PATHS = ["shop/prices.py", "shop/cart.py", "tools/json/loader.py", "src/utils/format.ts", "frontend/src/App.tsx", "go.mod", "cmd/app/main.go"]
GO_MOD = b"module github.com/acme/app\n\ngo 1.22\n\nrequire (\n\tgithub.com/google/uuid v1.6.0\n\tgithub.com/BurntSushi/toml v1.3.2 // indirect\n)\n"
LAYOUT = ProjectLayout.of(REPO_PATHS, lambda path: GO_MOD if path == "go.mod" else None)


def imported_at(path: str, source: str, line: int, text: str, occurrence: int = 0) -> Imported | None:
    language = language_for(path)
    assert language is not None
    row = source.split("\n")[line - 1]
    column = len(row[: _nth(row, text, occurrence)].encode())
    tree = parse(language, source.encode())
    node = identifier_at(language, tree, line - 1, column)
    return imported_symbol(language, tree, node) if node is not None else None


def _nth(row: str, text: str, occurrence: int) -> int:
    index = -1
    for _ in range(occurrence + 1):
        index = row.index(text, index + 1)
    return index


PYTHON = """import os.path
import numpy as np
from django.shortcuts import render, get_object_or_404 as get_or_404
from shop.prices import price
from . import cart

os.path.join("a")
np.array([1])
render(request)
get_or_404(Model)
price(item)
cart.total()
local.attribute
"""


@pytest.mark.parametrize(
    ("line", "text", "occurrence", "expected"),
    [
        (7, "join", 0, ("os", "path.join")),
        (7, "path", 0, ("os", "path")),
        (7, "os", 0, ("os", "")),
        (8, "array", 0, ("numpy", "array")),
        (9, "render", 0, ("django.shortcuts", "render")),
        (10, "get_or_404", 0, ("django.shortcuts", "get_object_or_404")),
        (3, "render", 0, ("django.shortcuts", "render")),
        (3, "get_object_or_404", 0, ("django.shortcuts", "get_object_or_404")),
        (3, "shortcuts", 0, ("django.shortcuts", "")),
        (11, "price", 0, ("shop.prices", "price")),
    ],
)
def test_python_names_resolve_to_their_import(line: int, text: str, occurrence: int, expected: tuple[str, str]) -> None:
    found = imported_at("app/views.py", PYTHON, line, text, occurrence)

    assert found is not None
    assert (found.module, found.name) == expected


@pytest.mark.parametrize(("line", "text"), [(12, "total"), (12, "cart"), (13, "attribute")])
def test_python_names_not_imported_or_imported_relatively_have_no_import(line: int, text: str) -> None:
    assert imported_at("app/views.py", PYTHON, line, text) is None


TYPESCRIPT = """import React, { useState as useLocalState, type FC } from "react"
import * as path from "node:path"
import { format } from "@/utils/format"
import { helper } from "./helper"
import { useQuery } from "@tanstack/react-query"

const Card: React.FC = () => {
  const [value] = useLocalState(path.join("a"))
  useQuery(format(helper()))
  return React.createElement("div")
}
"""


@pytest.mark.parametrize(
    ("line", "text", "expected"),
    [
        (8, "useLocalState", ("react", "useState")),
        (1, "useState", ("react", "useState")),
        (8, "join", ("node:path", "join")),
        (7, "FC", ("react", "FC")),
        (10, "createElement", ("react", "createElement")),
        (9, "useQuery", ("@tanstack/react-query", "useQuery")),
        (9, "format", ("@/utils/format", "format")),
    ],
)
def test_typescript_names_resolve_to_their_import(line: int, text: str, expected: tuple[str, str]) -> None:
    found = imported_at("frontend/src/Card.tsx", TYPESCRIPT, line, text)

    assert found is not None
    assert (found.module, found.name) == expected


def test_javascript_require_binds_names() -> None:
    source = 'const express = require("express")\nconst { join } = require("path")\nexpress.Router(join("a"))\n'

    router = imported_at("server.js", source, 3, "Router")
    join = imported_at("server.js", source, 3, "join")

    assert router == Imported("ecmascript", "express", "Router")
    assert join == Imported("ecmascript", "path", "join")


GO = """package main

import (
\t"fmt"
\thttp "net/http"
\t"github.com/google/uuid"
\t"github.com/acme/app/internal/store"
)

func main() {
\tfmt.Println(uuid.New(), store.Open())
\tvar request *http.Request
}
"""


@pytest.mark.parametrize(
    ("line", "text", "expected"),
    [
        (11, "Println", ("fmt", "Println")),
        (11, "New", ("github.com/google/uuid", "New")),
        (11, "Open", ("github.com/acme/app/internal/store", "Open")),
        (12, "Request", ("net/http", "Request")),
    ],
)
def test_go_names_resolve_to_their_import(line: int, text: str, expected: tuple[str, str]) -> None:
    found = imported_at("cmd/app/main.go", GO, line, text)

    assert found is not None
    assert (found.module, found.name) == expected


@pytest.mark.parametrize(
    ("imported", "external"),
    [
        (Imported("python", "django.shortcuts", "render"), True),
        (Imported("python", "os", "path.join"), True),
        (Imported("python", "json", "loads"), True),
        (Imported("python", "shop.prices", "price"), False),
        (Imported("ecmascript", "react", "useState"), True),
        (Imported("ecmascript", "node:path", "join"), True),
        (Imported("ecmascript", "@tanstack/react-query", "useQuery"), True),
        (Imported("ecmascript", "@/utils/format", "format"), False),
        (Imported("ecmascript", "./helper", "helper"), False),
        (Imported("ecmascript", "utils/format", "format"), False),
        (Imported("go", "fmt", "Println"), True),
        (Imported("go", "github.com/google/uuid", "New"), True),
        (Imported("go", "github.com/acme/app/internal/store", "Open"), False),
    ],
)
def test_imports_are_classified_as_in_repository_or_external(imported: Imported, external: bool) -> None:
    assert LAYOUT.is_external(imported) is external


def test_a_standard_library_name_is_external_unless_the_repository_shadows_it_at_its_root() -> None:
    shadowing = ProjectLayout.of(["json.py"], lambda _: None)

    assert shadowing.is_external(Imported("python", "json", "loads")) is False


def test_python_standard_library_links_to_its_documentation(tmp_path: Path) -> None:
    info = package_info(Imported("python", "os", "path.join"), tmp_path, ".", LAYOUT)

    assert (info.name, info.version, info.url) == ("os", None, "https://docs.python.org/3/library/os.html#os.path.join")


def test_python_packages_come_from_the_project_environment(tmp_path: Path) -> None:
    site = tmp_path / ".venv" / "lib" / "python3.12" / "site-packages"
    (site / "django").mkdir(parents=True)
    (site / "django" / "__init__.py").write_text("")
    (site / "django" / "shortcuts.py").write_text("import x\n\n\ndef render(request):\n    pass\n")
    metadata = site / "Django-5.1.dist-info"
    metadata.mkdir()
    metadata.joinpath("METADATA").write_text("Metadata-Version: 2.1\nName: Django\nVersion: 5.1\nProject-URL: Documentation, https://docs.djangoproject.com/\n")
    metadata.joinpath("top_level.txt").write_text("django\n")

    info = package_info(Imported("python", "django.shortcuts", "render"), tmp_path, ".", LAYOUT)

    assert (info.name, info.version, info.url) == ("Django", "5.1", "https://docs.djangoproject.com/")
    assert info.source == LibrarySource(str(site / "django" / "shortcuts.py"), 4)
    assert is_library_file(site / "django" / "shortcuts.py", tmp_path)


def test_python_packages_not_installed_link_to_pypi(tmp_path: Path) -> None:
    info = package_info(Imported("python", "requests", "get"), tmp_path, ".", LAYOUT)

    assert (info.name, info.version, info.url, info.source) == ("requests", None, "https://pypi.org/project/requests/", None)


def test_node_packages_come_from_the_nearest_node_modules(tmp_path: Path) -> None:
    package = tmp_path / "frontend" / "node_modules" / "react"
    package.mkdir(parents=True)
    package.joinpath("package.json").write_text(json.dumps({"version": "19.1.0", "homepage": "https://react.dev/", "main": "index.js"}))
    package.joinpath("index.js").write_text("module.exports = require('./cjs/react.js')\n")
    types = tmp_path / "frontend" / "node_modules" / "@types" / "react"
    types.mkdir(parents=True)
    types.joinpath("index.d.ts").write_text("export type FC = unknown\n\nexport function useState<S>(initial: S): [S, (value: S) => void]\n")

    info = package_info(Imported("ecmascript", "react", "useState"), tmp_path, "frontend/src", LAYOUT)

    assert (info.name, info.version, info.url) == ("react", "19.1.0", "https://react.dev/")
    assert info.source == LibrarySource(str(types / "index.d.ts"), 3)
    assert is_library_file(types / "index.d.ts", tmp_path)


def test_node_builtins_and_missing_packages_link_to_their_documentation(tmp_path: Path) -> None:
    builtin = package_info(Imported("ecmascript", "node:path", "join"), tmp_path, ".", LAYOUT)
    missing = package_info(Imported("ecmascript", "@tanstack/react-query", "useQuery"), tmp_path, ".", LAYOUT)

    assert (builtin.name, builtin.url) == ("path", "https://nodejs.org/api/path.html")
    assert (missing.name, missing.url, missing.source) == ("@tanstack/react-query", "https://www.npmjs.com/package/@tanstack/react-query", None)


def test_go_modules_take_their_version_from_go_mod_and_source_from_the_module_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOMODCACHE", str(tmp_path / "mod"))
    module = tmp_path / "mod" / "github.com" / "!burnt!sushi" / "toml@v1.3.2"
    module.mkdir(parents=True)
    module.joinpath("decode.go").write_text("package toml\n\n// Decode decodes.\nfunc Decode(data string, v any) error {\n\treturn nil\n}\n")

    info = package_info(Imported("go", "github.com/BurntSushi/toml", "Decode"), tmp_path, ".", LAYOUT)

    assert (info.name, info.version, info.url) == ("github.com/BurntSushi/toml", "v1.3.2", "https://pkg.go.dev/github.com/BurntSushi/toml#Decode")
    assert info.source == LibrarySource(str(module / "decode.go"), 4)
    assert is_library_file(module / "decode.go", tmp_path)


def test_go_standard_library_comes_from_goroot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOROOT", str(tmp_path / "go"))
    package = tmp_path / "go" / "src" / "fmt"
    package.mkdir(parents=True)
    package.joinpath("print.go").write_text("package fmt\n\nfunc Println(a ...any) {}\n")
    package.joinpath("print_test.go").write_text("package fmt\n\nfunc Println() {}\n")

    info = package_info(Imported("go", "fmt", "Println"), tmp_path, ".", LAYOUT)

    assert (info.name, info.url) == ("fmt", "https://pkg.go.dev/fmt#Println")
    assert info.source == LibrarySource(str(package / "print.go"), 3)


def test_only_installed_library_files_can_be_read(tmp_path: Path) -> None:
    (tmp_path / "secret.py").write_text("token = 1\n")
    (tmp_path / "node_modules" / "left-pad").mkdir(parents=True)
    (tmp_path / "node_modules" / "left-pad" / "index.js").write_text("module.exports = 1\n")
    (tmp_path / "node_modules" / "left-pad" / "notes.txt").write_text("text\n")

    assert is_library_file(tmp_path / "node_modules" / "left-pad" / "index.js", tmp_path)
    assert not is_library_file(tmp_path / "node_modules" / "left-pad" / "notes.txt", tmp_path)
    assert not is_library_file(tmp_path / "secret.py", tmp_path)
    assert not is_library_file(tmp_path / "node_modules" / ".." / "secret.py", tmp_path)
    assert not is_library_file(tmp_path / "node_modules" / "missing.js", tmp_path)


def test_a_python_environment_linked_from_outside_the_repository_is_not_served(tmp_path: Path) -> None:
    project, outside = tmp_path / "project", tmp_path / "home"
    (outside / "notes").mkdir(parents=True)
    (outside / "notes" / "secret.py").write_text("token = 1\n")
    project.mkdir()
    (project / ".venv").symlink_to(outside)

    assert not is_library_file(project / ".venv" / "notes" / "secret.py", project)
