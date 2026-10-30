import re

from tests.apiclient import ApiClient, Json, comment_on
from tests.forge.conftest import FakeGh
from tests.gitrepo import GitFixture

BASE = {
    "app.py": "def total(items):\n    return 0\n\n\ndef count(items):\n    return 0\n",
    "util.py": "def double(value):\n    return value\n",
    "lib.py": "def name():\n    return ''\n",
}
HEAD = {
    "app.py": "def total(items):\n    return sum(items)\n\n\ndef count(items):\n    return len(items)\n",
    "util.py": "def double(value):\n    return value * 2\n",
    "lib.py": "def name():\n    return 'lib'\n",
}


def setup_review(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> int:
    git_repo.commit(BASE)
    git_repo.git("remote", "add", "origin", "git@github.com:acme/widgets.git")
    git_repo.branch("feature")
    point_pull_request_at(fake_gh, git_repo.commit(HEAD))
    fake_gh.configure(files=[{"filename": path, "patch": ""} for path in sorted(HEAD)])
    review = api.start_review()
    api.call("PUT", f"/reviews/{review}/forge", body={"pr_number": 7})
    return review


def point_pull_request_at(fake_gh: FakeGh, head: str) -> None:
    fake_gh.configure(
        prs=[
            {
                "number": 7,
                "title": "Totals",
                "url": "https://github.com/acme/widgets/pull/7",
                "headRefOid": head,
                "headRefName": "feature",
                "baseRefName": "main",
            }
        ]
    )


def sync(api: ApiClient, review: int) -> Json:
    return api.call("POST", f"/reviews/{review}/sync")


def viewed(fake_gh: FakeGh) -> list[str]:
    return fake_gh.state().get("viewed", [])


def mark_calls(fake_gh: FakeGh, mutation: str = "markFileAsViewed") -> list[list[str]]:
    calls = [call["args"] for call in fake_gh.calls() if any(f" {mutation}(input" in arg for arg in call["args"])]
    return [[arg.split("=", 1)[1] for arg in args if re.match(r"^p\d+=", arg)] for args in calls]


def setup_many(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh, count: int) -> int:
    names = [f"m{index:02}.py" for index in range(count)]
    git_repo.commit(dict.fromkeys(names, "def f():\n    return 0\n"))
    git_repo.git("remote", "add", "origin", "git@github.com:acme/widgets.git")
    git_repo.branch("feature")
    point_pull_request_at(fake_gh, git_repo.commit(dict.fromkeys(names, "def f():\n    return 1\n")))
    fake_gh.configure(files=[{"filename": name, "patch": ""} for name in names])
    review = api.start_review()
    api.call("PUT", f"/reviews/{review}/forge", body={"pr_number": 7})
    for unit in api.units(review):
        api.call("POST", f"/reviews/{review}/approvals", 201, {"unit_id": unit["id"]})
    return review


def test_sync_marks_fully_approved_files_as_viewed_in_one_call(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    api.approve(review, "util.py::double")
    api.approve(review, "lib.py::name")

    result = sync(api, review)

    assert (result["marked_viewed"], result["not_viewed"], result["viewed_error"]) == (["lib.py", "util.py"], {}, None)
    assert mark_calls(fake_gh) == [["lib.py", "util.py"]]
    assert any("pullRequestId=PR_7" in arg for call in fake_gh.calls() for arg in call["args"])
    assert sorted(viewed(fake_gh)) == ["lib.py", "util.py"]


def test_partly_approved_files_stay_not_viewed(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    api.approve(review, "app.py::total")
    api.approve(review, "util.py::double")

    result = sync(api, review)

    assert result["marked_viewed"] == ["util.py"]
    assert viewed(fake_gh) == ["util.py"]


def test_file_approved_by_selected_lines_counts_as_fully_approved(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    git_repo.commit({"notes.txt": "one\n"})
    review = setup_review(api, git_repo, fake_gh)
    git_repo.commit({"notes.txt": "one\ntwo\nthree\n"})
    point_pull_request_at(fake_gh, git_repo.git("rev-parse", "HEAD"))
    fake_gh.configure(files=[{"filename": "notes.txt", "patch": ""}])
    api.refresh(review)
    api.approve_rows(review, "notes.txt", head_range=(2, 2))
    assert sync(api, review)["marked_viewed"] == []

    api.approve_rows(review, "notes.txt", head_range=(3, 3))

    assert sync(api, review)["marked_viewed"] == ["notes.txt"]


def test_files_changed_after_approval_stay_not_viewed(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    api.approve(review, "util.py::double")
    api.approve(review, "lib.py::name")
    point_pull_request_at(fake_gh, git_repo.commit({"util.py": "def double(value):\n    return value + value\n"}))

    result = sync(api, review)

    assert result["refresh"]["created"] is True
    assert result["marked_viewed"] == ["lib.py"]
    assert viewed(fake_gh) == ["lib.py"]


def test_files_already_viewed_on_github_are_left_as_they_are(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(viewed=["app.py", "util.py"])
    api.approve(review, "util.py::double")

    result = sync(api, review)

    assert (result["marked_viewed"], result["not_viewed"]) == ([], {})
    assert mark_calls(fake_gh) == []
    assert viewed(fake_gh) == ["app.py", "util.py"]


def test_a_file_that_cannot_be_marked_does_not_fail_the_sync(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(fail_viewed=["lib.py"])
    api.approve(review, "util.py::double")
    api.approve(review, "lib.py::name")

    result = sync(api, review)

    assert result["marked_viewed"] == ["util.py"]
    assert result["not_viewed"] == {"lib.py": "Could not mark lib.py as viewed"}
    assert mark_calls(fake_gh) == [["lib.py", "util.py"]]
    assert viewed(fake_gh) == ["util.py"]


def test_a_refused_request_is_not_retried_file_by_file(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_many(api, git_repo, fake_gh, 51)
    fake_gh.configure(fail_viewed_request="HTTP 403: Resource not accessible by integration")

    result = sync(api, review)

    assert (result["marked_viewed"], result["not_viewed"]) == ([], {})
    assert result["viewed_error"] == "HTTP 403: Resource not accessible by integration"
    assert [len(paths) for paths in mark_calls(fake_gh)] == [50]


def test_files_are_marked_fifty_per_request(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_many(api, git_repo, fake_gh, 51)

    result = sync(api, review)

    assert len(result["marked_viewed"]) == 51
    assert [len(paths) for paths in mark_calls(fake_gh)] == [50, 1]


def test_files_missing_from_the_pull_request_are_skipped_quietly(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(files=[{"filename": "app.py", "patch": ""}, {"filename": "lib.py", "patch": ""}])
    api.approve(review, "util.py::double")
    api.approve(review, "lib.py::name")

    result = sync(api, review)

    assert (result["marked_viewed"], result["not_viewed"], result["viewed_error"]) == (["lib.py"], {}, None)
    assert mark_calls(fake_gh) == [["lib.py"]]


def test_a_missing_file_list_is_reported_once(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(files_unavailable=True)
    api.approve(review, "util.py::double")

    result = sync(api, review)

    assert (result["marked_viewed"], result["not_viewed"]) == ([], {})
    assert result["viewed_error"] == "GitHub did not return the files of pull request #7"
    assert mark_calls(fake_gh) == []


def test_files_are_unmarked_when_the_pull_request_changes_while_marking(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(push_on_mark="e" * 40)
    api.approve(review, "util.py::double")
    api.approve(review, "lib.py::name")

    result = sync(api, review)

    assert result["marked_viewed"] == []
    assert "It changed while files were being marked, so they were unmarked" in result["viewed_error"]
    assert mark_calls(fake_gh, "unmarkFileAsViewed") == [["lib.py", "util.py"]]
    assert viewed(fake_gh) == []


def test_a_head_mismatch_already_reported_by_publishing_is_not_repeated(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    api.approve(review, "util.py::double")
    comment_on(api, review, "util.py::double", 1)
    point_pull_request_at(fake_gh, "f" * 40)
    fake_gh.clear_log()

    result = sync(api, review)

    assert result["publish_error"].startswith("The pull request head (ffffffff) differs")
    assert result["viewed_error"] is None
    assert not any("viewerViewedState" in arg for call in fake_gh.calls() for arg in call["args"])


def test_nothing_is_marked_while_the_pull_request_head_differs(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    api.approve(review, "util.py::double")
    point_pull_request_at(fake_gh, "f" * 40)

    result = sync(api, review)

    assert result["marked_viewed"] == []
    assert result["viewed_error"].startswith("The pull request head (ffffffff) differs")
    assert mark_calls(fake_gh) == []


def test_github_is_not_asked_when_no_file_is_fully_approved(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.clear_log()

    result = sync(api, review)

    assert result["marked_viewed"] == []
    assert not any("viewerViewedState" in arg for call in fake_gh.calls() for arg in call["args"])


def test_a_review_without_pull_request_marks_nothing(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    git_repo.commit(BASE)
    git_repo.branch("feature")
    git_repo.commit(HEAD)
    review = api.start_review()
    api.approve(review, "util.py::double")

    result = sync(api, review)

    assert result["marked_viewed"] == []
    assert fake_gh.calls() == []
