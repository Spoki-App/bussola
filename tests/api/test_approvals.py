from tests.apiclient import ApiClient
from tests.gitrepo import GitFixture

TWO_FUNCTIONS = "def first():\n    return 1\n\n\ndef second():\n    return 2\n"


def feature_with(git_repo: GitFixture, base: dict[str, str], change: dict[str, str]) -> None:
    git_repo.commit(base, "base")
    git_repo.branch("feature")
    git_repo.commit(change, "feature")


def test_approved_function_stays_approved_when_another_function_changes(api: ApiClient, git_repo: GitFixture) -> None:
    feature_with(git_repo, {"app.py": TWO_FUNCTIONS}, {"app.py": TWO_FUNCTIONS.replace("return 1", "return 10")})
    review = api.start_review()
    api.approve(review, "app.py::first")

    git_repo.commit({"app.py": TWO_FUNCTIONS.replace("return 1", "return 10").replace("return 2", "return 20")})
    api.refresh(review)

    assert api.states(review) == {"app.py::first": "approved", "app.py::second": "new"}


def test_modified_approved_function_is_changed_and_diff_shows_only_the_new_change(api: ApiClient, git_repo: GitFixture) -> None:
    body = "def first():\n    a = 1\n    b = 2\n    return a + b\n"
    feature_with(git_repo, {"app.py": "def first():\n    return 0\n"}, {"app.py": body})
    review = api.start_review()
    api.approve(review, "app.py::first")

    git_repo.commit({"app.py": body.replace("b = 2", "b = 3")})
    api.refresh(review)
    diff = api.diff(review, "app.py::first")

    assert api.states(review) == {"app.py::first": "changed"}
    assert diff["mode"] == "approved"
    changes = [(row["change"], row["text"]) for row in diff["rows"] if row["change"] != "context"]
    assert changes == [("removed", "    b = 2"), ("added", "    b = 3")]
    assert api.diff(review, "app.py::first", mode="base")["mode"] == "base"


def test_rebase_onto_new_base_keeps_unchanged_function_approved(api: ApiClient, git_repo: GitFixture) -> None:
    feature_with(git_repo, {"app.py": TWO_FUNCTIONS, "other.py": "x = 1\n"}, {"app.py": TWO_FUNCTIONS.replace("return 1", "return 10")})
    review = api.start_review()
    api.approve(review, "app.py::first")
    git_repo.checkout("main")
    git_repo.commit({"other.py": "x = 2\n"})
    git_repo.checkout("feature")

    git_repo.rebase("main")
    refreshed = api.refresh(review)

    assert refreshed["created"] is True
    assert api.states(review) == {"app.py::first": "approved"}


def test_force_push_with_rewritten_history_keeps_approval(api: ApiClient, git_repo: GitFixture) -> None:
    feature_with(git_repo, {"app.py": TWO_FUNCTIONS}, {"app.py": TWO_FUNCTIONS.replace("return 1", "return 10")})
    review = api.start_review()
    api.approve(review, "app.py::first")

    git_repo.git("reset", "-q", "--hard", "main")
    git_repo.commit({"notes.txt": "rewritten\n"}, "rewritten one")
    git_repo.commit({"app.py": TWO_FUNCTIONS.replace("return 1", "return 10")}, "rewritten two")
    api.refresh(review)

    assert api.states(review) == {"app.py::first": "approved", "notes.txt": "new"}


def test_renamed_function_with_identical_body_is_approved_moved(api: ApiClient, git_repo: GitFixture) -> None:
    added = "def helper(values):\n    return sorted(values)\n"
    feature_with(git_repo, {"app.py": TWO_FUNCTIONS}, {"app.py": TWO_FUNCTIONS + "\n\n" + added})
    review = api.start_review()
    api.approve(review, "app.py::helper")

    git_repo.commit({"app.py": TWO_FUNCTIONS + "\n\n" + added.replace("helper", "sort_values")})
    api.refresh(review)

    assert api.states(review) == {"app.py::sort_values": "approved_moved"}


def test_rename_of_existing_function_marks_both_halves_as_moved(api: ApiClient, git_repo: GitFixture) -> None:
    feature_with(git_repo, {"app.py": TWO_FUNCTIONS}, {"app.py": TWO_FUNCTIONS.replace("first", "primary")})
    review = api.start_review()

    before = api.states(review)
    api.approve(review, "app.py::primary")

    assert before == {"app.py::primary": "new", "app.py::first": "removed"}
    assert api.states(review) == {"app.py::primary": "approved", "app.py::first": "approved_moved"}


def test_deleted_function_is_removed_until_the_deletion_is_confirmed(api: ApiClient, git_repo: GitFixture) -> None:
    feature_with(git_repo, {"app.py": TWO_FUNCTIONS}, {"app.py": "def first():\n    return 1\n"})
    review = api.start_review()

    before = api.states(review)
    api.approve(review, "app.py::second")

    assert before == {"app.py::second": "removed"}
    assert api.states(review) == {"app.py::second": "approved"}


def test_approval_survives_base_change_with_informative_flag(api: ApiClient, git_repo: GitFixture) -> None:
    feature_with(git_repo, {"app.py": TWO_FUNCTIONS}, {"app.py": TWO_FUNCTIONS.replace("return 1", "return 10")})
    review = api.start_review()
    api.approve(review, "app.py::first")
    git_repo.checkout("main")
    git_repo.commit({"app.py": TWO_FUNCTIONS.replace("return 1", "return 5")})
    git_repo.checkout("feature")
    git_repo.git("merge", "-q", "-X", "ours", "main", "-m", "merge main")

    api.refresh(review)
    unit = api.unit(review, "app.py::first")

    assert unit["state"] == "approved"
    assert unit["base_changed"] is True


def test_revoked_approval_returns_the_unit_to_review(api: ApiClient, git_repo: GitFixture) -> None:
    feature_with(git_repo, {"app.py": TWO_FUNCTIONS}, {"app.py": TWO_FUNCTIONS.replace("return 1", "return 10")})
    review = api.start_review()
    approval = api.approve(review, "app.py::first")["approvals"][0]

    api.call("DELETE", f"/reviews/{review}/approvals/{approval['id']}")

    assert api.states(review) == {"app.py::first": "new"}


def test_approve_whole_file(api: ApiClient, git_repo: GitFixture) -> None:
    feature_with(git_repo, {"app.py": TWO_FUNCTIONS}, {"app.py": "import os\n\n\n" + TWO_FUNCTIONS.replace("return", "return -")})
    review = api.start_review()

    result = api.call("POST", f"/reviews/{review}/approvals", 201, {"path": "app.py"})

    assert len(result["approvals"]) == 3
    assert set(api.states(review).values()) == {"approved"}


def test_two_reviewers_have_separate_approvals(api: ApiClient, git_repo: GitFixture) -> None:
    feature_with(git_repo, {"app.py": TWO_FUNCTIONS}, {"app.py": TWO_FUNCTIONS.replace("return 1", "return 10")})
    review = api.start_review()
    api.approve(review, "app.py::first")

    git_repo.git("config", "user.email", "bob@example.com")
    git_repo.git("config", "user.name", "Bob")

    assert api.call("GET", "/me")["email"] == "bob@example.com"
    assert api.states(review) == {"app.py::first": "new"}


def test_since_last_review_shows_only_units_touched_afterwards(api: ApiClient, git_repo: GitFixture) -> None:
    three = TWO_FUNCTIONS + "\n\ndef third():\n    return 3\n"
    feature_with(git_repo, {"app.py": three}, {"app.py": three.replace("return 1", "return 10").replace("return 2", "return 20")})
    review = api.start_review()
    api.approve(review, "app.py::first")
    api.call("POST", f"/reviews/{review}/sessions", 201)

    git_repo.commit({"app.py": three.replace("return 1", "return 10").replace("return 2", "return 20").replace("return 3", "return 30")})
    api.refresh(review)

    assert api.states(review, "todo") == {"app.py::second": "new", "app.py::third": "new"}
    assert api.states(review, "since_last") == {"app.py::third": "new"}


def test_hidden_child_units_are_shown_as_a_readable_placeholder(api: ApiClient, git_repo: GitFixture) -> None:
    feature_with(git_repo, {"app.py": "import os\n\n\n" + TWO_FUNCTIONS}, {"app.py": "import sys\n\n\n" + TWO_FUNCTIONS})
    review = api.start_review()

    rows = api.diff(review, "app.py")["rows"]

    placeholders = [row for row in rows if row["placeholder"]]
    assert [row["text"] for row in placeholders] == ["\u22ef functions and classes, reviewed in their own cards"]
    assert placeholders[0]["old_line"] is None
    assert placeholders[0]["new_line"] is None
