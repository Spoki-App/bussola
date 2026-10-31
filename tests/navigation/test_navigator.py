from pathlib import Path

from bussola.navigation.navigator import Click, Navigator, Origin
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
