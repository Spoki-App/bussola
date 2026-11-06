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


def definitions_from(tmp_path: Path, git_repo: GitFixture, files: dict[str, str], path: str, clicked: str) -> list[tuple[str, int]]:
    commit = git_repo.commit(files)
    starter = ManualStarter()
    navigator = Navigator(tmp_path / "data", starter)
    navigator.prepare(git_repo.repo, commit, ())
    starter.run()
    line, text = next((number, text) for number, text in enumerate(files[path].split("\n"), start=1) if clicked in text)
    found = navigator.navigate(git_repo.repo, commit, (), Click(path, line, text.index(clicked) + len(clicked) - len("kind")))
    assert found.origin == Origin.REFERENCE
    return [(target.path, target.line) for target in found.targets]


SAME_NAME = {
    "plans.py": "def _kind(plan):\n    return plan.kind\n\n\ndef preview(plan, other):\n    return _kind(plan), other._kind()\n",
    "pixel.py": "def _kind(event):\n    return event\n",
    "pixel.ts": "export function kind(event: string): string {\n  return event\n}\n",
    "plans.ts": "function kind(plan: string): string {\n  return plan\n}\n\nexport const preview = (plan: string, other: Plan) => [kind(plan), other.kind()]\n",
    "pixel.go": "package shop\n\nfunc kind() int { return 1 }\n",
    "plans.go": "package shop\n\nfunc kind() int { return 2 }\n\nfunc preview(other Plan) int { return kind() + other.kind() }\n",
}


@pytest.mark.parametrize(
    ("path", "clicked", "expected"),
    [
        ("plans.py", "return _kind", [("plans.py", 1)]),
        ("plans.py", "other._kind", [("plans.py", 1), ("pixel.py", 1)]),
        ("plans.ts", "[kind", [("plans.ts", 1)]),
        ("plans.ts", "other.kind", [("plans.ts", 1), ("pixel.ts", 1)]),
        ("plans.go", "return kind", [("plans.go", 3)]),
        ("plans.go", "other.kind", [("plans.go", 3), ("pixel.go", 3)]),
    ],
)
def test_a_plain_name_defined_in_its_own_file_skips_namesakes_elsewhere(
    tmp_path: Path, git_repo: GitFixture, path: str, clicked: str, expected: list[tuple[str, int]]
) -> None:
    assert definitions_from(tmp_path, git_repo, SAME_NAME, path, clicked) == expected


def test_a_class_attribute_lists_its_usages(tmp_path: Path, git_repo: GitFixture) -> None:
    source = 'class Checkout:\n    BLOCKED = (\n        "Not now"\n    )\n\n    def check(self):\n        return self.BLOCKED\n'
    commit = git_repo.commit({"checkout.py": source})
    starter = ManualStarter()
    navigator = Navigator(tmp_path / "data", starter)
    navigator.prepare(git_repo.repo, commit, ())
    starter.run()

    found = navigator.navigate(git_repo.repo, commit, (), Click("checkout.py", 2, 5))

    assert (found.symbol, found.origin) == ("BLOCKED", Origin.DEFINITION)
    assert [(target.line, target.enclosing) for target in found.targets] == [(7, Enclosing(UnitKind.METHOD, "Checkout.check"))]
