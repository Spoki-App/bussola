import pytest

from rtool.git import ChangeStatus, GitRepo, InvalidRefError
from tests.gitrepo import GitFixture


@pytest.mark.parametrize("ref", ["--output=/tmp/x", "-n", "", "main\nHEAD", "does-not-exist"])
def test_invalid_refs_are_rejected(git_repo: GitFixture, ref: str) -> None:
    git_repo.commit({"a.txt": "a"})

    with pytest.raises(InvalidRefError):
        git_repo.repo.resolve_commit(ref)


def test_resolve_commit_returns_full_sha(git_repo: GitFixture) -> None:
    sha = git_repo.commit({"a.txt": "a"})

    assert git_repo.repo.resolve_commit("main") == sha


def test_discover_finds_root_from_subdirectory(git_repo: GitFixture) -> None:
    git_repo.commit({"pkg/mod/a.py": "x = 1\n"})

    assert GitRepo.discover(git_repo.root / "pkg" / "mod").root.resolve() == git_repo.root.resolve()


def test_changed_files_reports_added_modified_deleted_and_renamed(git_repo: GitFixture) -> None:
    base = git_repo.commit({"keep.txt": "1\n", "gone.txt": "bye\n", "old name.py": "def f():\n    return 1\n" * 5})
    git_repo.move("old name.py", "new name.py")
    head = git_repo.commit({"keep.txt": "2\n", "gone.txt": None, "fresh.txt": "hi\n"})

    changes = {change.path: change for change in git_repo.repo.changed_files(base, head)}

    assert {path: change.status for path, change in changes.items()} == {
        "fresh.txt": ChangeStatus.ADDED,
        "gone.txt": ChangeStatus.DELETED,
        "keep.txt": ChangeStatus.MODIFIED,
        "new name.py": ChangeStatus.RENAMED,
    }
    renamed = changes["new name.py"]
    assert renamed.old is not None
    assert renamed.old.path == "old name.py"


def test_blob_reader_reads_several_blobs_in_one_process(git_repo: GitFixture) -> None:
    base = git_repo.commit({"a.txt": "alpha\n"})
    head = git_repo.commit({"a.txt": "beta\n", "b.bin": b"\x00\x01\x02"})
    changes = git_repo.repo.changed_files(base, head)

    with git_repo.repo.blob_reader() as reader:
        contents = {change.path: reader.read(change.new.object_id) for change in changes if change.new}

    assert contents == {"a.txt": b"beta\n", "b.bin": b"\x00\x01\x02"}


def test_merge_base_and_first_commit(git_repo: GitFixture) -> None:
    root = git_repo.commit({"a.txt": "a"})
    fork = git_repo.commit({"a.txt": "b"})
    git_repo.branch("feature")
    git_repo.commit({"b.txt": "b"})
    git_repo.checkout("main")
    git_repo.commit({"c.txt": "c"})

    assert git_repo.repo.merge_base("main", "feature") == fork
    assert git_repo.repo.first_commit() == root
