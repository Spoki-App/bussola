from pathlib import Path

from bussola.navigation.navigator import Click, Enclosing, Navigator, Origin
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


def usages_with_enclosing(tmp_path: Path, git_repo: GitFixture, files: dict[str, str], path: str, line: int) -> list[tuple[int, Enclosing | None]]:
    commit = git_repo.commit(files)
    starter = ManualStarter()
    navigator = Navigator(tmp_path / "data", starter)
    navigator.prepare(git_repo.repo, commit, ())
    starter.run()
    column = files[path].split("\n")[line - 1].index("helper") + 1
    found = navigator.navigate(git_repo.repo, commit, (), Click(path, line, column))
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


def test_python_usages_name_the_function_method_or_class_they_live_in(tmp_path: Path, git_repo: GitFixture) -> None:
    usages = usages_with_enclosing(tmp_path, git_repo, {"shop.py": PYTHON_USAGES}, "shop.py", 1)

    assert usages == [
        (5, Enclosing(UnitKind.MODULE, "")),
        (9, Enclosing(UnitKind.CLASS, "Cart")),
        (12, Enclosing(UnitKind.METHOD, "Cart.total")),
        (17, Enclosing(UnitKind.FUNCTION, "review")),
    ]


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


def test_typescript_usages_name_their_enclosing_unit(tmp_path: Path, git_repo: GitFixture) -> None:
    usages = usages_with_enclosing(tmp_path, git_repo, {"shop.ts": TYPESCRIPT_USAGES}, "shop.ts", 1)

    assert usages == [
        (5, Enclosing(UnitKind.MODULE, "")),
        (9, Enclosing(UnitKind.METHOD, "Cart.total")),
        (14, Enclosing(UnitKind.FUNCTION, "review")),
    ]


JAVASCRIPT_USAGES = """function helper() {
  return 1
}

class Cart {
  total() {
    return helper()
  }
}
"""


def test_javascript_usages_name_their_enclosing_unit(tmp_path: Path, git_repo: GitFixture) -> None:
    usages = usages_with_enclosing(tmp_path, git_repo, {"shop.js": JAVASCRIPT_USAGES}, "shop.js", 1)

    assert usages == [(7, Enclosing(UnitKind.METHOD, "Cart.total"))]


GO_USAGES = """package shop

func helper() int { return 1 }

var limit = helper()

type Cart struct{}

func (c *Cart) Total() int {
	return helper()
}
"""


def test_go_usages_name_their_enclosing_unit(tmp_path: Path, git_repo: GitFixture) -> None:
    usages = usages_with_enclosing(tmp_path, git_repo, {"shop.go": GO_USAGES}, "shop.go", 3)

    assert usages == [
        (5, Enclosing(UnitKind.MODULE, "")),
        (10, Enclosing(UnitKind.METHOD, "Cart.Total")),
    ]


def test_usages_in_a_file_that_does_not_parse_have_no_enclosing_unit(tmp_path: Path, git_repo: GitFixture) -> None:
    files = {"shop.py": "def helper():\n    return 1\n", "broken.py": "from shop import helper\n\ndef review(:\n    helper()\n"}

    usages = usages_with_enclosing(tmp_path, git_repo, files, "shop.py", 1)

    assert usages == [(1, None), (4, None)]
