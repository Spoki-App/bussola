from bussola.review.rows import DiffLine, LineChange, diff_lines

CONTEXT, ADDED, REMOVED = LineChange.CONTEXT, LineChange.ADDED, LineChange.REMOVED


def changes(lines: list[DiffLine]) -> list[tuple[LineChange, int | None, int | None]]:
    return [(line.change, line.old_index, line.new_index) for line in lines]


def test_lines_that_only_change_indentation_are_paired_side_by_side() -> None:
    old = ["for page in pages:", "    load(page)", "    return", "log()"]
    new = ["try:", "    for page in pages:", "        load(page)", "        return", "finally:", "    log()"]

    assert changes(diff_lines(old, new)) == [
        (ADDED, None, 0),
        (REMOVED, 0, None),
        (ADDED, None, 1),
        (REMOVED, 1, None),
        (ADDED, None, 2),
        (REMOVED, 2, None),
        (ADDED, None, 3),
        (ADDED, None, 4),
        (REMOVED, 3, None),
        (ADDED, None, 5),
    ]


def test_rewritten_lines_are_paired_in_order_and_equal_lines_stay_context() -> None:
    old = ["keep", "one", "two", "three", "end  "]
    new = ["keep", "uno", "dos", "end"]

    assert changes(diff_lines(old, new)) == [
        (CONTEXT, 0, 0),
        (REMOVED, 1, None),
        (ADDED, None, 1),
        (REMOVED, 2, None),
        (ADDED, None, 2),
        (REMOVED, 3, None),
        (CONTEXT, 4, 3),
    ]
