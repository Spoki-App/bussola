from pathlib import Path

import pytest

from bussola.navigation.navigator import Click, Navigator, Origin
from bussola.navigation.scopes import Enclosing
from bussola.units.model import UnitKind
from tests.gitrepo import GitFixture
from tests.navigation.test_index import ManualStarter

SOURCE = {"main.go": "package main\n\nfunc helper() int { return 1 }\n\nfunc main() { helper() }\n"}


def test_navigation_is_not_ready_while_the_index_builds(tmp_path: Path, git_repo: GitFixture) -> None:
    commit = git_repo.commit(SOURCE)
    starter = ManualStarter()
    navigator = Navigator(tmp_path / "data", starter)
    click = Click("main.go", 5, SOURCE["main.go"].split("\n")[4].index("helper") + 1)

    building = navigator.navigate(git_repo.repo, commit, (), click)
    starter.run()
    ready = navigator.navigate(git_repo.repo, commit, (), click)

    assert (building.ready, building.symbol, building.origin, building.targets) == (False, "helper", Origin.REFERENCE, ())
    assert building.missing_server is not None
    assert building.missing_server.install == "go install golang.org/x/tools/gopls@latest"
    assert ready.ready
    assert [(target.path, target.line, target.preview) for target in ready.targets] == [("main.go", 3, "func helper() int { return 1 }")]


def usages_with_enclosing(tmp_path: Path, git_repo: GitFixture, files: dict[str, str], path: str) -> list[tuple[int, Enclosing | None]]:
    commit = git_repo.commit(files)
    starter = ManualStarter()
    navigator = Navigator(tmp_path / "data", starter)
    navigator.prepare(git_repo.repo, commit, ())
    starter.run()
    line, text = next((number, text) for number, text in enumerate(files[path].split("\n"), start=1) if "helper" in text)
    found = navigator.navigate(git_repo.repo, commit, (), Click(path, line, text.index("helper") + 1))
    assert found.origin == Origin.DEFINITION
    return [(target.line, target.enclosing) for target in found.targets]


PYTHON_USAGES = """def helper():
    return 1


LIMIT = helper()


class Cart:
    size = helper()

    def total(self):
        return helper()


def review():
    def inner():
        return helper()
    return inner
"""


TYPESCRIPT_USAGES = """export function helper(): number {
  return 1
}

const limit = helper()

export class Cart {
  total(): number {
    return helper()
  }
}

export function review(): number {
  return helper()
}
"""


JAVASCRIPT_USAGES = """function helper() {
  return 1
}

class Cart {
  total() {
    return helper()
  }
}
"""


GO_USAGES = """package shop

func helper() int { return 1 }

var limit = helper()

type Cart struct{}

func (c *Cart) Total() int {
	return helper()
}
"""


PYTHON_SCOPES = """import sys


def helper():
    return 1


if sys.version_info > (3,):
    def compat():
        return helper()


@register(helper)
def decorated(limit=helper()):
    pass


class Cart:
    @property
    def size(self):
        return 1

    @size.setter
    def size(self, value):
        helper()
"""


TYPESCRIPT_SCOPES = """export function helper(): number {
  return 1
}

export default {
  run() {
    return helper()
  },
}

describe('cart', () => {
  helper()
})

const total = () => helper()
"""


@pytest.mark.parametrize(
    ("path", "source", "expected"),
    [
        (
            "shop.py",
            PYTHON_USAGES,
            [
                (5, Enclosing(UnitKind.MODULE, "")),
                (9, Enclosing(UnitKind.CLASS, "Cart")),
                (12, Enclosing(UnitKind.METHOD, "Cart.total")),
                (17, Enclosing(UnitKind.FUNCTION, "review.inner")),
            ],
        ),
        (
            "shop.ts",
            TYPESCRIPT_USAGES,
            [(5, Enclosing(UnitKind.MODULE, "")), (9, Enclosing(UnitKind.METHOD, "Cart.total")), (14, Enclosing(UnitKind.FUNCTION, "review"))],
        ),
        ("shop.js", JAVASCRIPT_USAGES, [(7, Enclosing(UnitKind.METHOD, "Cart.total"))]),
        ("inline.ts", "function helper() { return 1 }\nclass Cart { total() { return helper() } }\n", [(2, Enclosing(UnitKind.METHOD, "Cart.total"))]),
        ("shop.go", GO_USAGES, [(5, Enclosing(UnitKind.MODULE, "")), (10, Enclosing(UnitKind.METHOD, "Cart.Total"))]),
        (
            "scopes.py",
            PYTHON_SCOPES,
            [
                (10, Enclosing(UnitKind.FUNCTION, "compat")),
                (13, Enclosing(UnitKind.MODULE, "")),
                (14, Enclosing(UnitKind.MODULE, "")),
                (25, Enclosing(UnitKind.METHOD, "Cart.size")),
            ],
        ),
        (
            "scopes.ts",
            TYPESCRIPT_SCOPES,
            [(7, Enclosing(UnitKind.METHOD, "run")), (12, Enclosing(UnitKind.MODULE, "")), (15, Enclosing(UnitKind.FUNCTION, "total"))],
        ),
    ],
)
def test_usages_name_the_function_method_or_class_they_live_in(
    tmp_path: Path, git_repo: GitFixture, path: str, source: str, expected: list[tuple[int, Enclosing]]
) -> None:
    assert usages_with_enclosing(tmp_path, git_repo, {path: source}, path) == expected


def test_usages_in_a_file_that_does_not_parse_have_no_enclosing_unit(tmp_path: Path, git_repo: GitFixture) -> None:
    files = {"shop.py": "def helper():\n    return 1\n", "broken.py": "from shop import helper\n\ndef review(:\n    helper()\n"}

    usages = usages_with_enclosing(tmp_path, git_repo, files, "shop.py")

    assert usages == [(1, None), (4, None)]
