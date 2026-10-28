from tests.apiclient import ApiClient, comment_on, thread_anchor
from tests.gitrepo import GitFixture

BODY = "def total(items):\n    count = len(items)\n    result = sum(items)\n    return result\n"
OTHER = "\n\ndef other():\n    return 0\n"


def start(git_repo: GitFixture, api: ApiClient) -> int:
    git_repo.commit({"app.py": "def total(items):\n    return 0\n" + OTHER})
    git_repo.branch("feature")
    git_repo.commit({"app.py": BODY + OTHER})
    return api.start_review()


def test_thread_keeps_its_line_when_the_unit_is_unchanged(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)
    thread = comment_on(api, review, "app.py::total", 2)

    git_repo.commit({"app.py": BODY + OTHER.replace("return 0", "return 1")})
    api.refresh(review)
    anchor = thread_anchor(api, review, thread["id"])["anchor"]

    assert (anchor["line_offset"], anchor["outdated"], anchor["file_line"]) == (2, False, 3)
    assert anchor["unit_id"] == api.unit(review, "app.py::total")["id"]


def test_thread_follows_its_line_when_lines_move_inside_the_unit(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)
    thread = comment_on(api, review, "app.py::total", 2)

    git_repo.commit({"app.py": BODY.replace("    count = len(items)\n", "    items = list(items)\n    count = len(items)\n") + OTHER})
    api.refresh(review)
    anchor = thread_anchor(api, review, thread["id"])["anchor"]

    assert (anchor["line_offset"], anchor["outdated"], anchor["file_line"]) == (3, False, 4)


def test_thread_becomes_outdated_when_its_line_is_deleted(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)
    thread = comment_on(api, review, "app.py::total", 2)

    git_repo.commit({"app.py": BODY.replace("    result = sum(items)\n    return result\n", "    return sum(items)\n") + OTHER})
    api.refresh(review)
    listed = thread_anchor(api, review, thread["id"])

    assert listed["anchor"]["outdated"] is True
    assert listed["line_text"] == "    result = sum(items)"
    assert listed["context_before"] == ["def total(items):", "    count = len(items)"]


def test_thread_follows_a_renamed_unit(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)
    thread = comment_on(api, review, "app.py::total", 1)

    git_repo.commit({"app.py": BODY.replace("def total", "def summed") + OTHER})
    api.refresh(review)
    listed = thread_anchor(api, review, thread["id"])

    assert listed["qualified_name"] == "summed"
    assert listed["anchor"]["unit_id"] == api.unit(review, "app.py::summed")["id"]
    assert api.unit(review, "app.py::summed")["open_threads"] == 1


def test_duplicate_lines_pick_the_occurrence_with_matching_context(api: ApiClient, git_repo: GitFixture) -> None:
    body = "def f():\n    a = 1\n    log()\n    b = 2\n    log()\n    return a + b\n"
    git_repo.commit({"app.py": "def f():\n    pass\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": body})
    review = api.start_review()
    thread = comment_on(api, review, "app.py::f", 4)

    git_repo.commit({"app.py": body.replace("    a = 1\n", "    a = 1\n    c = 3\n")})
    api.refresh(review)

    assert thread_anchor(api, review, thread["id"])["anchor"]["line_offset"] == 5


def test_review_and_file_threads_and_replies(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)

    general = api.call("POST", f"/reviews/{review}/threads", 201, {"scope": "review", "body": "Looks good overall"})
    on_file = api.call("POST", f"/reviews/{review}/threads", 201, {"scope": "file", "path": "app.py", "body": "Split this file?"})
    api.call("POST", f"/threads/{general['id']}/comments", 201, {"body": "Agreed"})
    api.call("PATCH", f"/threads/{on_file['id']}", body={"status": "resolved"})
    summary = api.call("GET", f"/reviews/{review}")

    threads = {thread["id"]: thread for thread in api.call("GET", f"/reviews/{review}/threads")}
    assert [comment["body"] for comment in threads[general["id"]]["comments"]] == ["Looks good overall", "Agreed"]
    assert threads[on_file["id"]]["status"] == "resolved"
    assert (summary["open_threads"], summary["total_threads"]) == (1, 2)


def test_only_the_author_can_edit_or_delete_a_comment(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)
    thread = api.call("POST", f"/reviews/{review}/threads", 201, {"scope": "review", "body": "First"})
    comment_id = thread["comments"][0]["id"]
    api.call("PATCH", f"/comments/{comment_id}", body={"body": "First, edited"})

    git_repo.git("config", "user.email", "bob@example.com")
    api.call("PATCH", f"/comments/{comment_id}", 403, {"body": "hijacked"})
    api.call("DELETE", f"/comments/{comment_id}", 403)
    git_repo.git("config", "user.email", "alice@example.com")
    deleted = api.call("DELETE", f"/comments/{comment_id}")

    assert deleted["deleted"] is True
    assert deleted["body"] == ""


def test_comments_must_not_be_empty(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)

    api.call("POST", f"/reviews/{review}/threads", 400, {"scope": "review", "body": "   "})


def test_thread_on_several_lines_keeps_its_range_when_lines_move(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)
    thread = comment_on(api, review, "app.py::total", (1, 2))

    created = thread_anchor(api, review, thread["id"])
    git_repo.commit({"app.py": BODY.replace("    count = len(items)\n", "    items = list(items)\n    count = len(items)\n") + OTHER})
    api.refresh(review)
    moved = thread_anchor(api, review, thread["id"])

    assert created["line_count"] == 2
    assert created["line_text"] == "    count = len(items)\n    result = sum(items)"
    assert created["context_after"] == ["    return result"]
    assert (created["anchor"]["file_line"], created["anchor"]["end_file_line"]) == (2, 3)
    assert (moved["anchor"]["file_line"], moved["anchor"]["end_file_line"]) == (3, 4)


def test_range_must_stay_inside_the_unit(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)
    unit_id = api.unit(review, "app.py::total")["id"]

    api.call("POST", f"/reviews/{review}/threads", 400, {"scope": "unit", "unit_id": unit_id, "line_offset": 2, "line_count": 5, "body": "x"})
