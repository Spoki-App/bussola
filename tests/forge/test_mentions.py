from tests.apiclient import ApiClient
from tests.forge.conftest import FIRST, FakeGh, GitHubSandbox
from tests.forge.test_conversation import start_review
from tests.gitrepo import GitFixture


def mention_calls(fake_gh: FakeGh) -> int:
    return sum(1 for call in fake_gh.calls() if any("assignableUsers" in arg for arg in call["args"]))


def test_pull_request_participants_come_before_collaborators(api: ApiClient, github: GitHubSandbox) -> None:
    github.open_pull_request({"app.py": FIRST})
    github.fake_gh.configure(requested_reviewers=["erin"], participants=["bob", "carol", "dave"], collaborators=["alice", "carol"])
    review = start_review(api)

    assert api.call("GET", f"/reviews/{review}/mentions") == ["bob", "erin", "carol", "dave", "alice"]


def test_branch_reviews_of_a_github_repository_offer_its_collaborators(api: ApiClient, github: GitHubSandbox) -> None:
    github.local.branch("feature")
    github.local.commit({"app.py": FIRST})
    github.fake_gh.configure(collaborators=["alice"])
    review = api.start_review()

    assert api.call("GET", f"/reviews/{review}/mentions") == ["alice"]


def test_branch_reviews_without_a_github_remote_have_no_mentions(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    git_repo.commit({"app.py": "x = 1\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": "x = 2\n"})
    review = api.start_review()

    assert api.call("GET", f"/reviews/{review}/mentions") == []
    assert mention_calls(fake_gh) == 0
