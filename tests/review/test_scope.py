from bussola.config import RepoConfig
from bussola.review.refs import resolve_review_commits
from bussola.review.scope import ChangeType, UnitChange, compute_scope
from bussola.units.extract import FileUnitExtractor
from tests.gitrepo import FileContent, GitFixture

FUNCTIONS = "import os\n\n\ndef first():\n    return 1\n\n\ndef second():\n    return 2\n"
SERVICE = "class Service:\n    retries = 1\n\n    def run(self):\n        return 1\n\n    def stop(self):\n        return 0\n"


def start_feature(git_repo: GitFixture, base_files: dict[str, FileContent]) -> None:
    git_repo.commit(base_files, "base")
    git_repo.branch("feature")


def scope(git_repo: GitFixture, config: RepoConfig | None = None) -> list[UnitChange]:
    commits = resolve_review_commits(git_repo.repo, "feature", "main")
    return compute_scope(git_repo.repo, commits.merge_base_sha, commits.head_sha, FileUnitExtractor(config or RepoConfig()))


def summary(changes: list[UnitChange]) -> set[tuple[ChangeType, str, str]]:
    return {(change.change_type, change.key.kind.value, str(change.key)) for change in changes}


def test_import_change_puts_module_unit_in_scope(git_repo: GitFixture) -> None:
    start_feature(git_repo, {"app.py": FUNCTIONS})
    git_repo.commit({"app.py": FUNCTIONS.replace("import os", "import sys")})

    assert summary(scope(git_repo)) == {(ChangeType.MODIFIED, "module", "app.py")}


def test_reordering_functions_changes_nothing(git_repo: GitFixture) -> None:
    start_feature(git_repo, {"app.py": FUNCTIONS})
    git_repo.commit({"app.py": "import os\n\n\ndef second():\n    return 2\n\n\ndef first():\n    return 1\n"})

    assert scope(git_repo) == []


def test_adding_a_function_next_to_others_leaves_module_unchanged(git_repo: GitFixture) -> None:
    start_feature(git_repo, {"app.py": FUNCTIONS})
    git_repo.commit({"app.py": FUNCTIONS + "\n\ndef third():\n    return 3\n"})

    assert summary(scope(git_repo)) == {(ChangeType.ADDED, "function", "app.py::third")}


def test_method_key_is_class_dot_method(git_repo: GitFixture) -> None:
    start_feature(git_repo, {"service.py": SERVICE})
    git_repo.commit({"service.py": SERVICE.replace("return 1", "return 2")})

    assert summary(scope(git_repo)) == {(ChangeType.MODIFIED, "method", "service.py::Service.run")}


def test_class_attribute_change_only_changes_class_unit(git_repo: GitFixture) -> None:
    start_feature(git_repo, {"service.py": SERVICE})
    git_repo.commit({"service.py": SERVICE.replace("retries = 1", "retries = 3")})

    assert summary(scope(git_repo)) == {(ChangeType.MODIFIED, "class", "service.py::Service")}


def test_deleted_function_is_removed(git_repo: GitFixture) -> None:
    start_feature(git_repo, {"app.py": FUNCTIONS})
    git_repo.commit({"app.py": "import os\n\n\ndef first():\n    return 1\n"})

    assert summary(scope(git_repo)) == {(ChangeType.REMOVED, "function", "app.py::second")}


def test_migrations_unsupported_and_binary_files_are_file_units(git_repo: GitFixture) -> None:
    start_feature(git_repo, {"README.md": "start\n"})
    git_repo.commit({"app/migrations/0001_initial.py": "def forwards():\n    pass\n", "notes.txt": "hello\n", "logo.png": b"\x89PNG\x00\x01"})

    changes = scope(git_repo)

    assert summary(changes) == {
        (ChangeType.ADDED, "file", "app/migrations/0001_initial.py"),
        (ChangeType.ADDED, "file", "notes.txt"),
        (ChangeType.ADDED, "file", "logo.png"),
    }
    binary = next(change for change in changes if change.key.path == "logo.png")
    assert binary.head is not None
    assert binary.head.text is None


def test_syntax_error_falls_back_to_file_unit(git_repo: GitFixture) -> None:
    start_feature(git_repo, {"app.py": FUNCTIONS})
    git_repo.commit({"app.py": FUNCTIONS + "\ndef broken(:\n"})

    summaries = summary(scope(git_repo))

    assert (ChangeType.ADDED, "file", "app.py") in summaries
    assert (ChangeType.REMOVED, "function", "app.py::first") in summaries


def test_changes_already_merged_into_base_leave_scope_after_rebase(git_repo: GitFixture) -> None:
    start_feature(git_repo, {"app.py": FUNCTIONS})
    shared = FUNCTIONS.replace("return 1", "return 10")
    git_repo.commit({"app.py": shared}, "shared fix")
    git_repo.commit({"app.py": shared.replace("return 2", "return 20")}, "feature work")
    git_repo.checkout("main")
    git_repo.commit({"app.py": shared}, "shared fix on main")
    git_repo.checkout("feature")
    git_repo.rebase("main")

    assert summary(scope(git_repo)) == {(ChangeType.MODIFIED, "function", "app.py::second")}


def test_renamed_file_keeps_unchanged_units_out_of_scope(git_repo: GitFixture) -> None:
    start_feature(git_repo, {"old.py": FUNCTIONS})
    git_repo.move("old.py", "new.py")
    git_repo.commit({"new.py": FUNCTIONS.replace("return 2", "return 3")})

    changes = scope(git_repo)

    assert summary(changes) == {(ChangeType.MODIFIED, "function", "new.py::second")}
    assert changes[0].old_path == "old.py"


def test_ignored_paths_are_skipped(git_repo: GitFixture) -> None:
    start_feature(git_repo, {"README.md": "start\n"})
    git_repo.commit({"vendor/lib.js": "function f() {}\n", "app.ts": "export const x = 1\n"})

    assert summary(scope(git_repo, RepoConfig(ignore=("vendor/**",)))) == {(ChangeType.ADDED, "module", "app.ts")}
