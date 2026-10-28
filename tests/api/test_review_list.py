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
