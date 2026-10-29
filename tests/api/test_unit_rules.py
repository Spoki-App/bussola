import pytest

from rtool.units.registry import EXTRACTORS_BY_SUFFIX
from tests.apiclient import ApiClient
from tests.gitrepo import GitFixture

GO_BEFORE = "package billing\n\nfunc Total() int {\n\treturn 0\n}\n"
GO_AFTER = "package billing\n\nfunc Total() int {\n\treturn 1\n}\n"


def test_refresh_splits_units_again_when_a_language_is_added(api: ApiClient, git_repo: GitFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    git_repo.commit({"billing.go": GO_BEFORE})
    git_repo.branch("feature")
    git_repo.commit({"billing.go": GO_AFTER})
    with monkeypatch.context() as patch:
        patch.delitem(EXTRACTORS_BY_SUFFIX, ".go")
        review = api.start_review()
        before = [(unit["kind"], unit["qualified_name"]) for unit in api.units(review)]

    refreshed = api.refresh(review)
    unchanged = api.refresh(review)

    assert before == [("file", "")]
    assert (refreshed["created"], refreshed["revision"]["number"]) == (True, 2)
    assert [(unit["kind"], unit["qualified_name"]) for unit in api.units(review)] == [("function", "Total")]
    assert (unchanged["created"], unchanged["revision"]["number"]) == (False, 2)


def test_rule_changes_that_do_not_touch_the_review_keep_its_revision(api: ApiClient, git_repo: GitFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    git_repo.commit({"app.py": "def f():\n    return 1\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": "def f():\n    return 2\n"})
    with monkeypatch.context() as patch:
        patch.delitem(EXTRACTORS_BY_SUFFIX, ".go")
        review = api.start_review()

    refreshed = api.refresh(review)

    assert (refreshed["created"], refreshed["revision"]["number"]) == (False, 1)
