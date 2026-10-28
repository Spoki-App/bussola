import pytest

from rtool.forge.github import GitHubAdapter, parse_patch_ranges
from tests.apiclient import ApiClient, Json, comment_on
from tests.forge.conftest import FakeGh
from tests.gitrepo import GitFixture

BASE = "def total(items):\n    return 0\n\n\ndef other():\n    return 0\n"
HEAD = "def total(items):\n    count = len(items)\n    result = sum(items)\n    return result\n\n\ndef other():\n    return 0\n"
WIDE_PATCH = "@@ -1,2 +1,4 @@\n def total(items):\n-    return 0\n+    count = len(items)\n+    result = sum(items)\n+    return result\n"
NARROW_PATCH = "@@ -1,2 +1,2 @@\n def total(items):\n-    return 0\n+    count = len(items)\n"


def setup_review(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh, patch: str = WIDE_PATCH) -> int:
    git_repo.commit({"app.py": BASE})
    git_repo.git("remote", "add", "origin", "git@github.com:acme/widgets.git")
    git_repo.branch("feature")
    head = git_repo.commit({"app.py": HEAD})
    pull = {
        "number": 7,
        "title": "Add totals",
        "url": "https://github.com/acme/widgets/pull/7",
        "headRefOid": head,
        "headRefName": "feature",
        "baseRefName": "main",
    }
    fake_gh.configure(prs=[pull], files=[{"filename": "app.py", "patch": patch}])
    return api.start_review()


def link(api: ApiClient, review: int) -> None:
    api.call("PUT", f"/reviews/{review}/forge", body={"pr_number": 7})


def publish(api: ApiClient, review: int, *, draft: bool = False, expected: int = 200) -> Json:
    return api.call("POST", f"/reviews/{review}/forge/publish", expected, {"draft": draft})


def test_overview_detects_repository_and_candidate_pull_requests(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)

    overview = api.call("GET", f"/reviews/{review}/forge")

    assert overview["status"]["authenticated"] is True
    assert overview["repository"] == "acme/widgets"
    assert [candidate["number"] for candidate in overview["candidates"]] == [7]
    assert overview["link"] is None


def test_linking_a_pull_request_reports_whether_heads_match(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)

    overview = api.call("PUT", f"/reviews/{review}/forge", body={"pr_number": 7})

    assert overview["link"] == {"provider": "github", "repository": "acme/widgets", "pr_number": 7}
    assert overview["head_matches"] is True


def test_publish_sends_one_review_with_inline_file_and_body_comments(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    comment_on(api, review, "app.py::total", 2, "Rename `result`?")
    api.call("POST", f"/reviews/{review}/threads", 201, {"scope": "file", "path": "app.py", "body": "Split this module"})
    api.call("POST", f"/reviews/{review}/threads", 201, {"scope": "review", "body": "Nice work overall"})

    result = publish(api, review)

    review_post = fake_gh.api_posts("/reviews")[0]["input"]
    assert review_post["event"] == "COMMENT"
    assert review_post["body"] == "Nice work overall"
    assert review_post["comments"] == [{"path": "app.py", "line": 3, "side": "RIGHT", "body": "Rename `result`?"}]
    file_post = fake_gh.api_posts("/pulls/7/comments")[0]["input"]
    assert file_post == {"body": "Split this module", "commit_id": git_repo.git("rev-parse", "feature"), "path": "app.py", "subject_type": "file"}
    assert sorted(outcome["status"] for outcome in result["outcomes"]) == ["published", "published", "published"]
    assert api.call("GET", f"/reviews/{review}")["unsent_comments"] == 0


def test_publishing_twice_sends_nothing_new(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    comment_on(api, review, "app.py::total", 2)
    publish(api, review)
    fake_gh.clear_log()

    result = publish(api, review)

    assert result["outcomes"] == []
    assert fake_gh.api_posts("/reviews") == []


def test_replies_and_edits_follow_published_threads(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    thread = comment_on(api, review, "app.py::total", 2, "First")
    publish(api, review)
    api.call("POST", f"/threads/{thread['id']}/comments", 201, {"body": "Second"})
    api.call("PATCH", f"/comments/{thread['comments'][0]['id']}", body={"body": "First, edited"})
    fake_gh.clear_log()

    result = publish(api, review)

    reply = fake_gh.api_posts("/replies")[0]
    edit = next(call for call in fake_gh.calls() if "PATCH" in call["args"])
    assert reply["input"] == {"body": "Second"}
    assert reply["args"][3].endswith("/comments/1002/replies")
    assert edit["input"] == {"body": "First, edited"}
    assert sorted(outcome["status"] for outcome in result["outcomes"]) == ["published", "updated"]


def test_line_outside_the_pull_request_diff_becomes_a_file_comment(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh, patch=NARROW_PATCH)
    link(api, review)
    comment_on(api, review, "app.py::total", 3, "Return directly")

    publish(api, review)

    file_post = fake_gh.api_posts("/pulls/7/comments")[0]["input"]
    assert file_post["subject_type"] == "file"
    assert file_post["body"].startswith("On `total`, line 4:")
    assert "Return directly" in file_post["body"]
    assert fake_gh.api_posts("/reviews") == []


def test_draft_review_is_left_pending(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    comment_on(api, review, "app.py::total", 2)

    publish(api, review, draft=True)

    assert "event" not in fake_gh.api_posts("/reviews")[0]["input"]


def test_publish_is_blocked_when_the_pull_request_head_differs(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    comment_on(api, review, "app.py::total", 2)
    git_repo.commit({"app.py": HEAD + "\n"})
    api.refresh(review)

    error = publish(api, review, expected=409)

    assert "Push the branch or refresh" in str(error["detail"])
    assert fake_gh.api_posts("/reviews") == []


def test_failed_remote_call_is_reported_and_retried_later(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    api.call("POST", f"/reviews/{review}/threads", 201, {"scope": "file", "path": "app.py", "body": "Split"})
    fake_gh.configure(fail_on=["/pulls/7/comments"])

    failed = publish(api, review)
    fake_gh.configure(fail_on=[])
    retried = publish(api, review)

    assert [outcome["status"] for outcome in failed["outcomes"]] == ["failed"]
    assert "422" in failed["outcomes"][0]["detail"]
    assert [outcome["status"] for outcome in retried["outcomes"]] == ["published"]


@pytest.mark.usefixtures("without_gh")
def test_missing_gh_is_reported(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"app.py": BASE})
    git_repo.branch("feature")
    git_repo.commit({"app.py": HEAD})
    review = api.start_review()

    status = api.call("GET", f"/reviews/{review}/forge")["status"]

    assert status["available"] is False
    assert "gh" in status["message"]


@pytest.mark.parametrize(
    ("remote_url", "expected"),
    [
        ("git@github.com:acme/widgets.git", "acme/widgets"),
        ("https://github.com/acme/widgets", "acme/widgets"),
        ("ssh://git@github.com/acme/widgets.git", "acme/widgets"),
        ("https://gitlab.com/acme/widgets.git", None),
        ("git@github.com:acme/widgets;rm -rf.git", None),
    ],
)
def test_repository_is_parsed_from_github_remotes_only(remote_url: str, expected: str | None) -> None:
    assert GitHubAdapter().repository_for(remote_url) == expected


def test_patch_ranges_cover_each_hunk_side() -> None:
    ranges = parse_patch_ranges("@@ -1,2 +1,4 @@\n x\n@@ -10 +12,0 @@\n-y\n")

    assert ranges.right == ((1, 4),)
    assert ranges.left == ((1, 2), (10, 10))


def test_thread_on_several_lines_becomes_a_multi_line_review_comment(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    comment_on(api, review, "app.py::total", (1, 2), "Merge these")

    publish(api, review)

    assert fake_gh.api_posts("/reviews")[0]["input"]["comments"] == [
        {"path": "app.py", "start_line": 2, "start_side": "RIGHT", "line": 3, "side": "RIGHT", "body": "Merge these"}
    ]


def test_range_leaving_the_pull_request_diff_names_its_lines(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh, patch=NARROW_PATCH)
    link(api, review)
    comment_on(api, review, "app.py::total", (1, 3), "Simplify")

    publish(api, review)

    body = fake_gh.api_posts("/pulls/7/comments")[0]["input"]["body"]
    assert body.startswith("On `total`, lines 2-4:")
    assert "    count = len(items)\n    result = sum(items)\n    return result" in body


def sync(api: ApiClient, review: int) -> Json:
    return api.call("POST", f"/reviews/{review}/sync")


def test_sync_checks_for_commits_then_sends_unsent_comments(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    comment_on(api, review, "app.py::total", 2, "Rename `result`?")
    assert api.call("GET", f"/reviews/{review}")["unsent_comments"] == 1

    result = sync(api, review)

    assert result["refresh"]["revision"]["number"] == 1
    assert [outcome["status"] for outcome in result["published"]["outcomes"]] == ["published"]
    assert fake_gh.api_posts("/reviews")[0]["input"]["event"] == "COMMENT"
    assert (result["publish_error"], result["unsent_comments"]) == (None, 0)
    assert api.call("GET", f"/reviews/{review}")["unsent_comments"] == 0


def test_sync_without_unsent_comments_sends_nothing(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)

    assert sync(api, review)["published"] is None
    assert fake_gh.api_posts("/reviews") == []


def test_sync_of_an_unlinked_review_keeps_comments_unsent(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    comment_on(api, review, "app.py::total", 2, "Rename `result`?")

    result = sync(api, review)

    assert (result["published"], result["unsent_comments"]) == (None, 1)


def test_sync_reports_why_comments_were_not_sent(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    comment_on(api, review, "app.py::total", 2, "Rename `result`?")
    git_repo.commit({"app.py": HEAD + "\n\ndef extra():\n    return 1\n"})

    result = sync(api, review)

    assert result["refresh"]["created"] is True
    assert "differs from the reviewed head" in result["publish_error"]
    assert result["unsent_comments"] == 1
