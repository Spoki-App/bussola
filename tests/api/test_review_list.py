from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.apiclient import ApiClient
from tests.gitrepo import GitFixture


@contextmanager
def counted_queries() -> Generator[list[str]]:
    statements: list[str] = []

    def record(*args: Any) -> None:
        statements.append(str(args[2]))

    event.listen(Engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(Engine, "before_cursor_execute", record)


def list_reviews(api: ApiClient, repo: int) -> int:
    with counted_queries() as statements:
        api.call("GET", f"/repos/{repo}/reviews")
    return len(statements)


def test_listing_reviews_does_not_query_per_review(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"app.py": "def total():\n    return 0\n"})
    for name in ("one", "two", "three"):
        git_repo.branch(name, "main")
        git_repo.commit({"app.py": f"def total():\n    return '{name}'\n"})
    repo = api.call("POST", "/repos", 201, {"path": str(api.git.root)})["id"]
    api.call("POST", f"/repos/{repo}/reviews", 201, {"head_ref": "one", "base_ref": "main"})
    with_one = list_reviews(api, repo)

    for name in ("two", "three"):
        api.call("POST", f"/repos/{repo}/reviews", 201, {"head_ref": name, "base_ref": "main"})

    assert list_reviews(api, repo) == with_one
    assert [review["total"] for review in api.call("GET", f"/repos/{repo}/reviews")] == [1, 1, 1]


def test_a_diff_reads_only_its_own_approved_text(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"app.py": "def one():\n    return 1\n\n\ndef two():\n    return 2\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": "def one():\n    return 10\n\n\ndef two():\n    return 20\n"})
    review = api.start_review()
    api.approve(review, "app.py::one")
    api.approve(review, "app.py::two")
    git_repo.commit({"app.py": "def one():\n    return 11\n\n\ndef two():\n    return 21\n"})
    api.refresh(review)

    with counted_queries() as statements:
        diff = api.diff(review, "app.py::one")

    texts = [statement for statement in statements if "approved_text" in statement]
    assert diff["mode"] == "approved"
    assert len(texts) == 1
    assert "WHERE approvals.id" in texts[0]
