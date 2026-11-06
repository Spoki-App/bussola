from tests.apiclient import ApiClient
from tests.forge.conftest import FakeGh
from tests.forge.test_publish import link, setup_review
from tests.gitrepo import GitFixture


def thread_with(*logins: str) -> dict[str, object]:
    return {"comments": {"nodes": [{"author": {"login": login}} for login in logins]}}


def mention_calls(fake_gh: FakeGh) -> int:
    return sum(1 for call in fake_gh.calls() if any("assignableUsers" in arg for arg in call["args"]))


def test_pull_request_participants_come_before_collaborators(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    link(api, review)
    state = fake_gh.state()
    state["prs"][0]["author"] = {"login": "bob"}
    conversation = {"reviews": [{"author": {"login": "carol"}}], "comments": [{"author": None}], "reviewThreads": [thread_with("dave", "bob")]}
    fake_gh.configure(prs=state["prs"], conversation=conversation, requested_reviewers=["erin"], collaborators=["alice", "carol"])

    candidates = api.call("GET", f"/reviews/{review}/mentions")

    assert candidates == ["bob", "erin", "carol", "dave", "alice"]


def test_mentions_are_fetched_once_per_review(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(collaborators=["alice"])

    first = api.call("GET", f"/reviews/{review}/mentions")
    second = api.call("GET", f"/reviews/{review}/mentions")

    assert first == second == ["alice"]
    assert mention_calls(fake_gh) == 1


def test_branch_reviews_without_a_github_remote_have_no_mentions(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    git_repo.commit({"app.py": "x = 1\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": "x = 2\n"})
    review = api.start_review()

    assert api.call("GET", f"/reviews/{review}/mentions") == []
    assert mention_calls(fake_gh) == 0
