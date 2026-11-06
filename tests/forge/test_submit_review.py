from tests.apiclient import ApiClient, Json, comment_on
from tests.forge.conftest import FakeGh
from tests.forge.test_publish import link, setup_review
from tests.gitrepo import GitFixture


def submit(api: ApiClient, review: int, event: str, body: str = "", expected: int = 200) -> Json:
    return api.call("POST", f"/reviews/{review}/forge/review", expected, {"event": event, "body": body})


def test_approve_sends_pending_comments_in_the_same_review(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    comment_on(api, review, "app.py::total", 2, "Rename `result`?")
    api.call("POST", f"/reviews/{review}/threads", 201, {"scope": "review", "body": "Nice work overall"})

    result = submit(api, review, "APPROVE", "Looks good")

    posts = fake_gh.api_posts("/reviews")
    assert len(posts) == 1
    assert posts[0]["input"]["event"] == "APPROVE"
    assert posts[0]["input"]["body"] == "Looks good\n\n---\n\nNice work overall"
    assert posts[0]["input"]["comments"] == [{"path": "app.py", "line": 3, "side": "RIGHT", "body": "Rename `result`?"}]
    assert result["event"] == "APPROVE"
    assert result["published"]["review_url"].startswith("https://github.com/acme/widgets/pull/7#pullrequestreview-")
    assert result["unsent_comments"] == 0
    assert api.call("GET", f"/reviews/{review}")["unsent_comments"] == 0


def test_approve_and_comment_with_only_a_summary(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)

    submit(api, review, "APPROVE")
    submit(api, review, "COMMENT", "  A question on the naming  ")

    posts = [post["input"] for post in fake_gh.api_posts("/reviews")]
    assert [(post["event"], post["body"], post["comments"]) for post in posts] == [("APPROVE", "", []), ("COMMENT", "A question on the naming", [])]


def test_request_changes_needs_a_summary(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    comment_on(api, review, "app.py::total", 2)

    error = submit(api, review, "REQUEST_CHANGES", "   ", expected=400)

    assert "summary" in error["detail"]
    assert fake_gh.api_posts("/reviews") == []
    assert api.call("GET", f"/reviews/{review}")["unsent_comments"] == 1


def test_comment_needs_a_summary_or_a_pending_comment(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)

    submit(api, review, "COMMENT", expected=400)
    comment_on(api, review, "app.py::total", 2)
    submit(api, review, "COMMENT")

    assert [post["input"]["event"] for post in fake_gh.api_posts("/reviews")] == ["COMMENT"]


def test_a_refused_review_keeps_the_comments_unsent(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    comment_on(api, review, "app.py::total", 2)
    fake_gh.configure(fail_on=["/pulls/7/reviews"])

    error = submit(api, review, "REQUEST_CHANGES", "Please fix", expected=502)

    assert "422" in error["detail"]
    assert api.call("GET", f"/reviews/{review}")["unsent_comments"] == 1


def test_a_moved_head_stops_the_review(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    comment_on(api, review, "app.py::total", 2)
    fake_gh.configure(prs=[{**fake_gh.state()["prs"][0], "headRefOid": "f" * 40}])

    error = submit(api, review, "APPROVE", expected=409)

    assert "differs from the reviewed head" in error["detail"]
    assert fake_gh.api_posts("/reviews") == []
    assert api.call("GET", f"/reviews/{review}")["unsent_comments"] == 1


def test_a_review_needs_a_linked_pull_request(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)

    submit(api, review, "APPROVE", expected=409)


def test_overview_names_the_github_user(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    fake_gh.configure(viewer="carol")

    assert api.call("GET", f"/reviews/{review}/forge")["viewer"] == "carol"
