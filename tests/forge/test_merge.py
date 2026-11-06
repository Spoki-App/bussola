from typing import Any

from tests.apiclient import ApiClient, Json
from tests.forge.conftest import FakeGh
from tests.forge.test_viewed import setup_review
from tests.gitrepo import GitFixture


def merge_options(api: ApiClient, review: int) -> Json:
    return api.call("GET", f"/reviews/{review}/forge/merge")


def merge(api: ApiClient, review: int, expected: int = 200, **body: Any) -> Json:
    head = merge_options(api, review)["head_sha"]
    return api.call("POST", f"/reviews/{review}/forge/merge", expected, {"method": "squash", "head_sha": head, **body})


def pull_head(fake_gh: FakeGh) -> str:
    return fake_gh.state()["prs"][0]["headRefOid"]


def deleted_branches(fake_gh: FakeGh) -> list[str]:
    return fake_gh.state().get("deleted_branches", [])


def test_offers_only_the_methods_the_repository_allows(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(merge_settings={"mergeCommitAllowed": False, "viewerDefaultMergeMethod": "REBASE"})

    options = merge_options(api, review)

    assert (options["methods"], options["default_method"]) == (["squash", "rebase"], "rebase")
    assert options["commit_texts"] == {"squash": {"title": "Totals (#7)", "message": "* contribution"}}
    assert (options["blockers"], options["branch_deletion"]) == ([], "optional")


def test_default_method_falls_back_to_the_first_allowed_one(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(merge_settings={"mergeCommitAllowed": False, "viewerDefaultMergeMethod": "MERGE"})

    assert merge_options(api, review)["default_method"] == "squash"


def test_prefills_the_commit_text_of_merge_and_squash(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)

    texts = merge_options(api, review)["commit_texts"]

    assert texts == {
        "merge": {"title": "Merge pull request #7 from bob/feature", "message": "Totals"},
        "squash": {"title": "Totals (#7)", "message": "* contribution"},
    }


def test_explains_why_merging_is_blocked(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    status = {"mergeStateStatus": "BLOCKED", "reviewDecision": "REVIEW_REQUIRED", "statusCheckRollup": {"state": "FAILURE"}}
    fake_gh.configure(merge_status=status)

    assert merge_options(api, review)["blockers"] == ["An approving review is required.", "Some checks are failing."]

    fake_gh.configure(merge_status={"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY", "isDraft": True})

    assert merge_options(api, review)["blockers"] == [
        "This pull request is still a draft.",
        "This branch has conflicts with the base branch that must be resolved.",
    ]


def test_blocked_by_protection_rules_without_a_known_reason(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(merge_status={"mergeStateStatus": "BLOCKED"})

    assert merge_options(api, review)["blockers"] == ["The branch protection rules of the base branch block merging."]


def test_squash_merges_with_the_edited_text_and_refreshes_the_state(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)

    result = merge(api, review, title="Sum the totals (#7)", message="")

    assert result == {"state": "MERGED", "branch_deleted": False, "branch_error": None}
    assert fake_gh.state()["merged"] == {"merge_method": "squash", "sha": pull_head(fake_gh), "commit_message": "", "commit_title": "Sum the totals (#7)"}
    assert api.call("GET", f"/reviews/{review}")["pull_request"]["state"] == "MERGED"
    assert deleted_branches(fake_gh) == []


def test_rebase_sends_no_commit_text(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)

    merge(api, review, method="rebase", title="ignored", message="ignored")

    assert fake_gh.state()["merged"] == {"merge_method": "rebase", "sha": pull_head(fake_gh)}


def test_deletes_the_head_branch_after_merging(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)

    result = merge(api, review, delete_branch=True)

    assert (result["state"], result["branch_deleted"]) == ("MERGED", True)
    assert deleted_branches(fake_gh) == ["acme/widgets:feature"]


def test_leaves_deletion_to_github_when_the_repository_deletes_merged_branches(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(merge_settings={"deleteBranchOnMerge": True})

    assert merge_options(api, review)["branch_deletion"] == "automatic"
    assert merge(api, review, delete_branch=True)["branch_deleted"] is True
    assert deleted_branches(fake_gh) == []


def test_reports_a_branch_that_could_not_be_deleted(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(fail_on=["git/refs/heads"])

    result = merge(api, review, delete_branch=True)

    assert result["state"] == "MERGED"
    assert result["branch_error"] == "The pull request was merged, but its branch could not be deleted: HTTP 422: Unprocessable Entity"


def test_a_refused_merge_shows_the_reason_from_github(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(merge_error="Pull Request is not mergeable (HTTP 405)")

    error = merge(api, review, 502)

    assert error["detail"] == "Pull Request is not mergeable (HTTP 405)"
    assert api.call("GET", f"/reviews/{review}")["pull_request"]["state"] != "MERGED"


def test_refuses_a_head_that_moved_since_the_options_were_read(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)

    error = api.call("POST", f"/reviews/{review}/forge/merge", 502, {"method": "merge", "head_sha": "0" * 40})

    assert "Head branch was modified" in error["detail"]


def test_refuses_a_method_the_repository_does_not_allow(api: ApiClient, git_repo: GitFixture, fake_gh: FakeGh) -> None:
    review = setup_review(api, git_repo, fake_gh)
    fake_gh.configure(merge_settings={"rebaseMergeAllowed": False})

    error = merge(api, review, 400, method="rebase")

    assert error["detail"] == "This repository does not allow the rebase merge method"
    assert "merged" not in fake_gh.state()
