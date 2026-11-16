from bussola.review.ai_review import GroupLimit, review_groups
from bussola.storage.models import UnitSnapshot


def unit(number: int) -> UnitSnapshot:
    snapshot = UnitSnapshot(
        revision_id=1,
        path="app.py",
        old_path=None,
        kind="function",
        qualified_name=f"f{number}",
        base_hash="b",
        head_hash="h",
        base_text="def f(): ...",
        head_text="def f(): pass",
        base_lines=[],
        head_lines=[],
    )
    snapshot.id = number
    return snapshot


def test_definitions_groups_hold_at_most_the_given_number_of_units() -> None:
    units = [unit(number) for number in range(1, 6)]

    groups = review_groups(units, units, {}, dict.fromkeys(range(1, 6), 10), GroupLimit(1_000, 2))

    assert [[snapshot.id for snapshot in group] for group in groups] == [[1, 2], [3, 4], [5]]


def test_groups_are_split_by_code_size() -> None:
    units = [unit(number) for number in range(1, 4)]

    groups = review_groups(units, units, {}, {1: 6, 2: 6, 3: 3}, GroupLimit(10))

    assert [[snapshot.id for snapshot in group] for group in groups] == [[1], [2, 3]]
