from tests.apiclient import ApiClient
from tests.gitrepo import GitFixture

BASE_CONFIG = "name = demo\nport = 80\nhost = local\n"
HEAD_CONFIG = "name = demo\nport = 8080\nhost = local\ndebug = true\n"


def start(git_repo: GitFixture, api: ApiClient) -> int:
    git_repo.commit({"settings.ini": BASE_CONFIG})
    git_repo.branch("feature")
    git_repo.commit({"settings.ini": HEAD_CONFIG})
    return api.start_review()


def test_selection_approves_only_changed_rows_inside_it(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)

    result = api.approve_rows(review, "settings.ini", head_range=(2, 2), base_range=(2, 2))
    unit = api.unit(review, "settings.ini")

    assert sorted(row["line_text"] for row in result["row_approvals"]) == ["port = 80", "port = 8080"]
    assert (unit["state"], unit["rows_approved"], unit["rows_total"]) == ("partial", 2, 3)


def test_covering_every_changed_row_approves_the_unit(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)
    api.approve_rows(review, "settings.ini", head_range=(2, 2), base_range=(2, 2))

    api.approve_rows(review, "settings.ini", head_range=(1, 4))

    assert api.states(review) == {"settings.ini": "approved"}


def test_diff_marks_approved_rows_and_revoking_selection_undoes_them(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)
    selection = api.approve_rows(review, "settings.ini", head_range=(4, 4))["row_approvals"][0]["selection_id"]

    approved = [row["text"] for row in api.diff(review, "settings.ini")["rows"] if row["approved"]]
    api.call("DELETE", f"/reviews/{review}/row-approvals/{selection}")

    assert approved == ["debug = true"]
    assert api.states(review) == {"settings.ini": "new"}


def test_new_edit_next_to_an_approved_row_needs_review_again(api: ApiClient, git_repo: GitFixture) -> None:
    review = start(git_repo, api)
    api.approve_rows(review, "settings.ini", head_range=(1, 4), base_range=(1, 3))

    git_repo.commit({"settings.ini": HEAD_CONFIG.replace("debug = true", "debug = true\nverbose = true")})
    api.refresh(review)
    unit = api.unit(review, "settings.ini")

    assert (unit["state"], unit["rows_approved"], unit["rows_total"]) == ("partial", 2, 4)


def test_module_code_can_be_approved_by_selection(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"app.py": "import os\n\n\ndef f():\n    return 1\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": "import os\nimport sys\n\n\ndef f():\n    return 1\n"})
    review = api.start_review()

    api.approve_rows(review, "app.py", head_range=(2, 2))

    assert api.states(review) == {"app.py": "approved"}


def test_functions_cannot_be_approved_by_selection(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"app.py": "def f():\n    return 1\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": "def f():\n    return 2\n"})
    review = api.start_review()
    unit_id = api.unit(review, "app.py::f")["id"]

    api.call("POST", f"/reviews/{review}/approvals", 400, {"unit_id": unit_id, "head_range": [2, 2]})


def test_units_say_which_approval_action_applies(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"settings.ini": BASE_CONFIG, "app.py": "def gone():\n    return 0\n\n\ndef total():\n    return 0\n"})
    git_repo.branch("feature")
    git_repo.commit({"settings.ini": HEAD_CONFIG, "app.py": "def total():\n    return 1\n"})
    review = api.start_review()

    def action(name: str) -> tuple[bool, str]:
        unit = api.unit(review, name)
        return unit["todo"], unit["action"]

    assert action("app.py::total") == (True, "approve")
    assert action("app.py::gone") == (True, "confirm_removal")
    api.approve(review, "app.py::total")
    assert action("app.py::total") == (False, "revoke")
    api.approve_rows(review, "settings.ini", head_range=(1, 4), base_range=(1, 3))
    assert action("settings.ini") == (False, "revoke_lines")
