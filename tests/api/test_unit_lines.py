from tests.apiclient import ApiClient
from tests.gitrepo import GitFixture


def test_units_carry_their_line_range_in_the_head_file(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"app.py": "def a():\n    return 1\n", "gone.txt": "x\n"})
    git_repo.branch("feature")
    git_repo.commit({"app.py": "import os\n\n\ndef a():\n    return 2\n\n\ndef b():\n    return 3\n", "gone.txt": None})
    review = api.start_review()

    lines = {f"{unit['path']}::{unit['qualified_name']}": (unit["head_start"], unit["head_end"]) for unit in api.units(review)}

    assert lines["app.py::a"] == (4, 5)
    assert lines["app.py::b"] == (8, 9)
    assert lines["gone.txt::"] == (None, None)
