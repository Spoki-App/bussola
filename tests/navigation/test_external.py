from pathlib import Path

import pytest

from bussola.navigation.external import Imported, ProjectLayout, imported_symbol, is_library_file
from bussola.navigation.symbols import identifier_at, language_for, parse

REPO_PATHS = [
    *("shop/prices.py", "shop/cart.py", "tools/json/loader.py", "proj/__init__.py", "proj/celery.py"),
    *("tsconfig.json", "src/utils/format.ts", "src/api/axios.ts", "frontend/src/App.tsx", "packages/ui/package.json", "packages/ui/index.ts"),
    *("go.mod", "cmd/app/main.go"),
]
GO_MOD = b"""module github.com/acme/app

go 1.22

require (
\tgithub.com/google/uuid v1.6.0
\tgithub.com/BurntSushi/toml v1.3.2 // indirect
)

require github.com/mattn/go-sqlite3 v1.14.22

replace (
\tgithub.com/google/uuid v1.5.0 => ../uuid
)
"""
TSCONFIG = b"""{
  // comments and trailing commas, as tsc allows
  "$schema": "https://json.schemastore.org/tsconfig",
  "compilerOptions": {
    "baseUrl": "src",
    "paths": {"@app/*": ["*"], "*": ["types/*"],},
  },
}
"""
FILES = {"go.mod": GO_MOD, "tsconfig.json": TSCONFIG, "packages/ui/package.json": b'{"name": "@acme/ui"}'}
LAYOUT = ProjectLayout.of(REPO_PATHS, FILES.get)


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
        (Imported("python", "proj.celery", "app"), False),
        (Imported("python", "celery", "shared_task"), True),
        (Imported("ecmascript", "react", "useState"), True),
        (Imported("ecmascript", "node:path", "join"), True),
        (Imported("ecmascript", "@tanstack/react-query", "useQuery"), True),
        (Imported("ecmascript", "@/utils/format", "format"), False),
        (Imported("ecmascript", "./helper", "helper"), False),
        (Imported("ecmascript", "utils/format", "format"), False),
        (Imported("ecmascript", "@app/utils/format", "format"), False),
        (Imported("ecmascript", "@acme/ui", "Button"), False),
        (Imported("ecmascript", "@acme/ui/theme", "colors"), False),
        (Imported("ecmascript", "axios", ""), True),
        (Imported("ecmascript", "lodash", "debounce"), True),
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


def test_go_requirements_ignore_replace_directives() -> None:
    assert LAYOUT.go_requirement("github.com/google/uuid") == ("github.com/google/uuid", "v1.6.0")
    assert LAYOUT.go_requirement("github.com/mattn/go-sqlite3") == ("github.com/mattn/go-sqlite3", "v1.14.22")


def test_go_package_names_drop_the_go_affixes_of_their_path() -> None:
    source = (
        'package main\n\nimport (\n\t"github.com/mattn/go-sqlite3"\n\t"github.com/redis/go-redis/v9"\n)\n\nfunc main() { sqlite3.Open(); redis.NewClient() }\n'
    )

    assert imported_at("main.go", source, 8, "Open") == Imported("go", "github.com/mattn/go-sqlite3", "Open")
    assert imported_at("main.go", source, 8, "NewClient") == Imported("go", "github.com/redis/go-redis/v9", "NewClient")
