import textwrap

import pytest

from bussola.review import moves as move_detection
from tests.apiclient import ApiClient, Json
from tests.gitrepo import GitFixture

TOTAL = """def total(items):
    subtotal = sum(item.price * item.quantity for item in items)
    discount = subtotal * 0.1 if subtotal > 100 else 0
    shipping = 0 if subtotal > 50 else 7
    return subtotal - discount + shipping
"""

CHECKOUT = """def checkout(cart, user):
    if not user.active:
        raise PermissionError("inactive user")
    for item in cart.items:
        if item.quantity <= 0:
            raise ValueError(f"bad quantity for {item.sku}")
        if item.price < 0:
            raise ValueError(f"bad price for {item.sku}")
    return cart.place_order(user)
"""

EXTRACTED = """def checkout(cart, user):
    if not user.active:
        raise PermissionError("inactive user")
    validate(cart)
    return cart.place_order(user)


def validate(cart):
    for item in cart.items:
        if item.quantity <= 0:
            raise ValueError(f"bad quantity for {item.sku}")
        if item.price < 0:
            raise ValueError(f"bad price for {item.sku}")
"""


def moves(api: ApiClient, review: int) -> list[Json]:
    return api.call("GET", f"/reviews/{review}/moves")


def described(move: Json) -> tuple[str, str, bool]:
    return (move["removed"]["qualified_name"], move["added"]["qualified_name"], move["identical"])


def test_a_function_moved_to_another_file_is_an_identical_move(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"cart.py": TOTAL, "prices.py": "RATE = 1\n"})
    git_repo.branch("feature")
    git_repo.commit({"cart.py": "", "prices.py": "RATE = 1\n\n\n" + TOTAL})
    review = api.start_review()

    [move] = moves(api, review)

    assert described(move) == ("total", "total", True)
    assert (move["removed"]["path"], move["removed"]["side"], move["removed"]["first_line"], move["removed"]["last_line"]) == ("cart.py", "base", 1, 5)
    assert (move["added"]["path"], move["added"]["side"], move["added"]["first_line"], move["added"]["last_line"]) == ("prices.py", "head", 4, 8)


def test_a_slightly_edited_move_is_found_but_not_identical(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"cart.py": TOTAL})
    git_repo.branch("feature")
    edited = TOTAL.replace("def total(items):", "def order_total(items):").replace("else 7", "else 9")
    git_repo.commit({"cart.py": edited})
    review = api.start_review()

    [move] = moves(api, review)

    assert described(move) == ("total", "order_total", False)
    assert move["similarity"] >= 0.8


def test_code_extracted_into_a_new_function_links_both_places(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"shop.py": CHECKOUT})
    git_repo.branch("feature")
    git_repo.commit({"shop.py": EXTRACTED})
    review = api.start_review()

    [move] = moves(api, review)

    assert described(move) == ("checkout", "validate", True)
    assert (move["removed"]["first_line"], move["removed"]["last_line"]) == (4, 8)
    assert (move["added"]["first_line"], move["added"]["last_line"]) == (9, 13)
    comparison = api.call("POST", f"/reviews/{review}/compare", body={"left": _request(move["removed"]), "right": _request(move["added"])})
    assert comparison["identical"]
    assert [(row["change"], row["old_line"], row["new_line"]) for row in comparison["rows"]] == [("context", line, line + 5) for line in range(4, 9)]


def test_small_or_unrelated_blocks_are_not_moves(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"a.py": "def a():\n    return 1\n", "b.py": TOTAL})
    git_repo.branch("feature")
    other = "def report(rows):\n    for row in rows:\n        print(row.name, row.value)\n    return len(rows)\n"
    git_repo.commit({"a.py": "", "c.py": "def c():\n    return 1\n", "b.py": other})
    review = api.start_review()

    assert moves(api, review) == []


def test_two_arbitrary_ranges_are_compared_line_by_line(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"cart.py": TOTAL})
    git_repo.branch("feature")
    git_repo.commit({"cart.py": TOTAL.replace("0.1", "0.2"), "other.py": "def other():\n    discount = 5\n"})
    review = api.start_review()
    total, other = api.unit(review, "cart.py::total"), api.unit(review, "other.py::other")

    body = {
        "left": {"unit_id": total["id"], "side": "base", "line_offset": 2, "line_count": 1},
        "right": {"unit_id": other["id"], "side": "head", "line_offset": 1, "line_count": 1},
    }
    comparison = api.call("POST", f"/reviews/{review}/compare", body=body)

    assert not comparison["identical"]
    assert [(row["change"], row["old_line"], row["new_line"]) for row in comparison["rows"]] == [("removed", 3, None), ("added", None, 2)]
    assert comparison["left"]["path"] == "cart.py"
    assert comparison["right"]["qualified_name"] == "other"


def test_a_range_outside_the_unit_is_rejected(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"cart.py": TOTAL})
    git_repo.branch("feature")
    git_repo.commit({"cart.py": TOTAL.replace("0.1", "0.2")})
    review = api.start_review()
    unit = api.unit(review, "cart.py::total")

    body = {
        "left": {"unit_id": unit["id"], "side": "head", "line_offset": 50, "line_count": 1},
        "right": {"unit_id": unit["id"], "side": "base", "line_offset": 0, "line_count": 1},
    }

    api.call("POST", f"/reviews/{review}/compare", 400, body)


def test_pasted_code_is_compared_with_a_range(api: ApiClient, git_repo: GitFixture) -> None:
    git_repo.commit({"cart.py": TOTAL})
    git_repo.branch("feature")
    git_repo.commit({"cart.py": TOTAL.replace("0.1", "0.2")})
    review = api.start_review()
    unit = api.unit(review, "cart.py::total")
    right = {"unit_id": unit["id"], "side": "head", "line_offset": 1, "line_count": 2}

    edited = "subtotal = sum(items)\r\ndiscount = subtotal * 0.2 if subtotal > 100 else 0\r\n"
    copied = textwrap.dedent("\n".join(TOTAL.replace("0.1", "0.2").splitlines()[1:3]))

    changed = api.call("POST", f"/reviews/{review}/compare", body={"pasted": edited, "right": right})
    same = api.call("POST", f"/reviews/{review}/compare", body={"pasted": copied, "right": right})

    assert changed["left"] is None
    assert not changed["identical"]
    assert [(row["change"], row["old_line"], row["new_line"]) for row in changed["rows"]] == [("removed", 1, None), ("added", None, 2), ("context", 2, 3)]
    assert "--- a/clipboard\n+++ b/cart.py\n" in changed["unified"]
    assert same["identical"]


@pytest.mark.parametrize("body", [{}, {"pasted": ""}, {"pasted": "x = 1", "left": {"unit_id": 1, "side": "head", "line_offset": 0, "line_count": 1}}])
def test_a_comparison_needs_exactly_one_left_side(api: ApiClient, git_repo: GitFixture, body: Json) -> None:
    git_repo.commit({"cart.py": TOTAL})
    git_repo.branch("feature")
    git_repo.commit({"cart.py": TOTAL.replace("0.1", "0.2")})
    review = api.start_review()
    unit = api.unit(review, "cart.py::total")

    api.call("POST", f"/reviews/{review}/compare", 422, {**body, "right": {"unit_id": unit["id"], "side": "head", "line_offset": 0, "line_count": 1}})


def _request(code: Json) -> Json:
    return {"unit_id": code["unit_id"], "side": code["side"], "line_offset": code["line_offset"], "line_count": code["line_count"]}


def test_very_long_units_are_skipped(api: ApiClient, git_repo: GitFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(move_detection, "MAX_UNIT_LINES", 3)
    git_repo.commit({"cart.py": TOTAL, "prices.py": "RATE = 1\n"})
    git_repo.branch("feature")
    git_repo.commit({"cart.py": "", "prices.py": "RATE = 1\n\n\n" + TOTAL})
    review = api.start_review()

    assert moves(api, review) == []


def test_a_long_range_can_be_compared(api: ApiClient, git_repo: GitFixture) -> None:
    long_file = "".join(f"line_{index} = {index}\n" for index in range(6000))
    git_repo.commit({"data.txt": long_file})
    git_repo.branch("feature")
    git_repo.commit({"data.txt": long_file.replace("line_5 = 5", "line_5 = 6")})
    review = api.start_review()
    unit = api.unit(review, "data.txt")

    body = {
        "left": {"unit_id": unit["id"], "side": "base", "line_offset": 0, "line_count": 6000},
        "right": {"unit_id": unit["id"], "side": "head", "line_offset": 0, "line_count": 6000},
    }
    comparison = api.call("POST", f"/reviews/{review}/compare", body=body)

    assert comparison["left"]["line_count"] == 6000
    assert not comparison["identical"]
