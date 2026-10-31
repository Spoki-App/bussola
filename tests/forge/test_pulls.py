from pathlib import Path
from typing import Any

import pytest

from tests.apiclient import ApiClient
from tests.forge.conftest import FIRST, SECOND, GitHubSandbox
from tests.gitrepo import GitFixture


def register(api: ApiClient) -> int:
    return api.call("POST", "/repos", 201, {"path": str(api.git.root)})["id"]


def unit_texts(api: ApiClient, review_id: int) -> list[Any]:
    return [api.diff(review_id, "app.py::total")["rows"][-1]["text"]]


def test_lists_open_pull_requests_of_the_github_remote(api: ApiClient, github: GitHubSandbox) -> None:
    github.open_pull_request({"app.py": FIRST})
    repo = register(api)

    listing = api.call("GET", f"/repos/{repo}/pulls")

    assert listing["repository"] == "acme/widgets"
    assert [(row["pull"]["number"], row["pull"]["author"], row["review_id"]) for row in listing["pulls"]] == [(7, "bob", None)]
    assert (listing["pulls"][0]["pull"]["comment_count"], listing["pulls"][0]["pull"]["unresolved_threads"]) == (6, 1)


def test_reviewing_a_pull_request_fetches_its_code_and_links_it(api: ApiClient, github: GitHubSandbox) -> None:
    head = github.open_pull_request({"app.py": FIRST})
    repo = register(api)

    review = api.call("POST", f"/repos/{repo}/pulls/7/review", 201)

    assert (review["head_ref"], review["base_ref"]) == ("refs/bussola/pull/7", "origin/main")
    assert review["latest_revision"]["head_sha"] == head
    assert review["pull_request"] == {
        "number": 7,
        "title": "Sum the items",
        "url": "https://github.com/acme/widgets/pull/7",
        "author": "bob",
        "state": "OPEN",
        "description": "Sums the items instead of returning zero.\n\n- [x] tested",
    }
    assert api.states(review["id"]) == {"app.py::total": "new"}
    assert api.call("GET", f"/repos/{repo}/pulls")["pulls"][0]["review_id"] == review["id"]
    assert api.call("GET", f"/reviews/{review['id']}/forge")["link"]["pr_number"] == 7
    assert "refs/bussola/pull/7" not in github.local.git("branch", "--all")


def test_reviewing_the_same_pull_request_again_reuses_the_review(api: ApiClient, github: GitHubSandbox) -> None:
    github.open_pull_request({"app.py": FIRST})
    repo = register(api)

    first = api.call("POST", f"/repos/{repo}/pulls/7/review", 201)
    second = api.call("POST", f"/repos/{repo}/pulls/7/review", 201)

    assert first["id"] == second["id"]


def test_sync_brings_in_new_commits_and_keeps_approvals_of_unchanged_units(api: ApiClient, github: GitHubSandbox) -> None:
    github.open_pull_request({"app.py": FIRST, "notes.txt": "hello\n"})
    repo = register(api)
    review = api.call("POST", f"/repos/{repo}/pulls/7/review", 201)["id"]
    api.approve(review, "notes.txt")

    github.open_pull_request({"app.py": SECOND})
    result = api.call("POST", f"/repos/{repo}/pulls/sync")

    assert result == {"updated": 1, "closed": 0, "failed": []}
    assert api.states(review) == {"app.py::total": "new", "notes.txt": "approved"}
    assert unit_texts(api, review) == ["    return sum(items, 0)"]


def test_sync_marks_merged_pull_requests_without_fetching(api: ApiClient, github: GitHubSandbox) -> None:
    github.open_pull_request({"app.py": FIRST})
    repo = register(api)
    review = api.call("POST", f"/repos/{repo}/pulls/7/review", 201)["id"]

    github.open_pull_request({"app.py": SECOND}, state="MERGED")
    result = api.call("POST", f"/repos/{repo}/pulls/sync")

    assert result == {"updated": 0, "closed": 1, "failed": []}
    assert api.call("GET", f"/reviews/{review}")["pull_request"]["state"] == "MERGED"
    assert unit_texts(api, review) == ["    return sum(items)"]


def test_refresh_with_fetch_updates_a_pull_request_review(api: ApiClient, github: GitHubSandbox) -> None:
    github.open_pull_request({"app.py": FIRST})
    repo = register(api)
    review = api.call("POST", f"/repos/{repo}/pulls/7/review", 201)["id"]
    github.open_pull_request({"app.py": SECOND})

    refreshed = api.call("POST", f"/reviews/{review}/refresh", body={"fetch": True})

    assert refreshed["created"] is True
    assert refreshed["revision"]["number"] == 2


def test_rejects_option_like_base_branch_names(api: ApiClient, github: GitHubSandbox) -> None:
    github.open_pull_request({"app.py": FIRST}, base="--upload-pack=touch pwned")
    repo = register(api)

    error = api.call("POST", f"/repos/{repo}/pulls/7/review", 400)

    assert "Unexpected base branch name" in error["detail"]


@pytest.mark.usefixtures("fake_gh")
def test_repository_without_github_remote_lists_nothing(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"a.txt": "a\n"})
    repo = register(api)

    listing = api.call("GET", f"/repos/{repo}/pulls")

    assert (listing["repository"], listing["pulls"]) == (None, [])


def open_link(api: ApiClient, url: str, expected: int = 201) -> Any:
    return api.call("POST", "/pulls/open", expected, {"url": url})


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/acme/widgets/pull/7",
        "github.com/Acme/Widgets/pull/7/files",
        "https://github.com/acme/widgets/pull/7#discussion_r1",
    ],
)
def test_a_pull_request_link_opens_its_review_in_the_matching_repository(api: ApiClient, github: GitHubSandbox, url: str) -> None:
    head = github.open_pull_request({"app.py": FIRST})
    repo = register(api)

    review = open_link(api, url)

    assert (review["repo_id"], review["pull_request"]["number"], review["latest_revision"]["head_sha"]) == (repo, 7, head)
    assert open_link(api, url)["id"] == review["id"]


def test_a_pull_request_link_finds_and_adds_a_clone_under_home(api: ApiClient, github: GitHubSandbox, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    github.open_pull_request({"app.py": FIRST})
    monkeypatch.setenv("HOME", str(tmp_path))

    review = open_link(api, "https://github.com/acme/widgets/pull/7")

    assert [repo["path"] for repo in api.call("GET", "/repos")] == [str(api.git.root.resolve())]
    assert review["pull_request"]["number"] == 7


def test_a_pull_request_link_without_a_local_clone_is_reported(api: ApiClient, github: GitHubSandbox, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    github.open_pull_request({"app.py": FIRST})
    monkeypatch.setenv("HOME", str(tmp_path / "data"))

    error = open_link(api, "https://github.com/acme/gadgets/pull/7", 404)

    assert "github.com/acme/gadgets" in error["detail"]
    assert error["code"] == "no_local_clone"


@pytest.mark.parametrize("url", ["https://github.com/acme/widgets/issues/7", "https://github.com/acme/widgets/pull/" + "9" * 1000])
def test_a_link_that_is_not_a_pull_request_is_rejected(api: ApiClient, url: str) -> None:
    error = open_link(api, url, 400)

    assert "Not a GitHub pull request link" in error["detail"]


def test_syncing_pull_requests_keeps_a_linked_branch_review_on_its_branch(api: ApiClient, github: GitHubSandbox) -> None:
    github.open_pull_request({"app.py": FIRST})
    github.local.branch("feature")
    github.local.commit({"app.py": SECOND})
    review = api.start_review()
    api.call("PUT", f"/reviews/{review}/forge", body={"pr_number": 7})
    repo = api.call("GET", "/repos")[0]["id"]

    result = api.call("POST", f"/repos/{repo}/pulls/sync")

    detail = api.call("GET", f"/reviews/{review}")
    assert (result["updated"], result["failed"]) == (1, [])
    assert (detail["head_ref"], detail["pull_request_review"], detail["pull_request"]["number"]) == ("feature", False, 7)
