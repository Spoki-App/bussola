from typing import Any

from tests.apiclient import ApiClient, Json
from tests.forge.conftest import FIRST, SECOND, GitHubSandbox

STAMP = "2026-10-28T10:00:00Z"


def note(remote_id: int, login: str, body: str) -> dict[str, Any]:
    return {
        "databaseId": remote_id,
        "author": {"login": login},
        "body": body,
        "createdAt": STAMP,
        "submittedAt": STAMP,
        "url": f"https://github.com/acme/widgets/pull/7#c{remote_id}",
    }


def review_thread(line: int | None, *notes: dict[str, Any], resolved: bool = False) -> dict[str, Any]:
    return {"isResolved": resolved, "path": "app.py", "line": line, "startLine": line, "diffSide": "RIGHT", "comments": {"nodes": list(notes)}}


def set_conversation(github: GitHubSandbox, head: str, threads: list[dict[str, Any]], comments: list[dict[str, Any]] | None = None) -> None:
    reviews = [note(77, "carol", "Looks good overall"), note(78, "carol", "")]
    conversation = {"headRefOid": head, "reviewThreads": threads, "comments": comments or [], "reviews": reviews}
    github.fake_gh.configure(conversation=conversation, viewer="alice-gh")


def start_review(api: ApiClient) -> int:
    repo = api.call("POST", "/repos", 201, {"path": str(api.git.root)})["id"]
    return api.call("POST", f"/repos/{repo}/pulls/7/review", 201)["id"]


def threads(api: ApiClient, review: int) -> list[Json]:
    return api.call("GET", f"/reviews/{review}/threads")


def test_github_comments_are_imported_when_reviewing_a_pull_request(api: ApiClient, github: GitHubSandbox) -> None:
    head = github.open_pull_request({"app.py": FIRST})
    set_conversation(github, head, [review_thread(2, note(501, "bob", "Why sum?"), note(502, "alice-gh", "Because"))], [note(900, "bob", "Nice PR")])

    review = start_review(api)

    imported = threads(api, review)
    inline = next(thread for thread in imported if thread["scope"] == "unit")
    assert (inline["qualified_name"], inline["anchor"]["file_line"]) == ("total", 2)
    assert [(comment["author"]["name"], comment["body"], comment["mine"]) for comment in inline["comments"]] == [
        ("bob", "Why sum?", False),
        ("Alice", "Because", True),
    ]
    assert inline["comments"][0]["remote_url"] == "https://github.com/acme/widgets/pull/7#c501"
    assert sorted(comment["body"] for thread in imported if thread["scope"] == "review" for comment in thread["comments"]) == ["Looks good overall", "Nice PR"]
    assert api.call("GET", f"/reviews/{review}/forge")["pending_comments"] == 0


def test_syncing_again_adds_only_new_replies_and_follows_resolution(api: ApiClient, github: GitHubSandbox) -> None:
    head = github.open_pull_request({"app.py": FIRST})
    first = note(501, "bob", "Why sum?")
    set_conversation(github, head, [review_thread(2, first)])
    review = start_review(api)
    repo = api.call("GET", "/repos")[0]["id"]

    set_conversation(github, head, [review_thread(2, first, note(503, "bob", "Never mind"), resolved=True)])
    api.call("POST", f"/repos/{repo}/pulls/sync")

    inline = next(thread for thread in threads(api, review) if thread["scope"] == "unit")
    assert [comment["body"] for comment in inline["comments"]] == ["Why sum?", "Never mind"]
    assert inline["status"] == "resolved"
    assert len(threads(api, review)) == 2


def test_outdated_github_comments_become_file_threads(api: ApiClient, github: GitHubSandbox) -> None:
    head = github.open_pull_request({"app.py": FIRST})
    set_conversation(github, head, [review_thread(None, note(501, "bob", "This was on old code"))])

    review = start_review(api)

    file_thread = next(thread for thread in threads(api, review) if thread["scope"] == "file")
    assert (file_thread["path"], file_thread["comments"][0]["body"]) == ("app.py", "This was on old code")


def test_lines_are_not_anchored_when_github_has_another_head(api: ApiClient, github: GitHubSandbox) -> None:
    github.open_pull_request({"app.py": FIRST})
    set_conversation(github, "0" * 40, [review_thread(2, note(501, "bob", "Why sum?"))])

    review = start_review(api)

    assert {thread["scope"] for thread in threads(api, review)} == {"file", "review"}


def test_reply_in_rtool_to_an_imported_thread_is_sent_as_a_github_reply(api: ApiClient, github: GitHubSandbox) -> None:
    head = github.open_pull_request({"app.py": FIRST})
    set_conversation(github, head, [review_thread(2, note(501, "bob", "Why sum?"))])
    review = start_review(api)
    inline = next(thread for thread in threads(api, review) if thread["scope"] == "unit")
    api.call("POST", f"/threads/{inline['id']}/comments", 201, {"body": "Because it is shorter"})
    github.fake_gh.configure(files=[{"filename": "app.py", "patch": "@@ -1,2 +1,2 @@\n def total(items):\n-    return 0\n+    return sum(items)\n"}])
    github.fake_gh.clear_log()

    api.call("POST", f"/reviews/{review}/forge/publish", body={"draft": False})

    reply = github.fake_gh.api_posts("/replies")[0]
    assert reply["args"][3].endswith("/comments/501/replies")
    assert reply["input"] == {"body": "Because it is shorter"}
    assert github.fake_gh.api_posts("/reviews") == []


def test_check_with_fetch_on_a_pull_request_review_imports_new_comments(api: ApiClient, github: GitHubSandbox) -> None:
    head = github.open_pull_request({"app.py": FIRST})
    set_conversation(github, head, [])
    review = start_review(api)

    new_head = github.open_pull_request({"app.py": SECOND})
    set_conversation(github, new_head, [review_thread(2, note(601, "bob", "Better"))])
    api.call("POST", f"/reviews/{review}/refresh", body={"fetch": True})

    inline = next(thread for thread in threads(api, review) if thread["scope"] == "unit")
    assert inline["comments"][0]["body"] == "Better"
