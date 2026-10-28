from difflib import SequenceMatcher

import pytest

from rtool.review import rows
from rtool.review.rows import LineChange, diff_lines


def test_line_diffs_are_computed_once_per_content(monkeypatch: pytest.MonkeyPatch) -> None:
    matchers: list[SequenceMatcher[str]] = []

    def counting(isjunk: None, a: list[str], b: list[str], autojunk: bool) -> SequenceMatcher[str]:
        matcher = SequenceMatcher(isjunk, a, b, autojunk=autojunk)
        matchers.append(matcher)
        return matcher

    monkeypatch.setattr(rows, "SequenceMatcher", counting)
    old, new = ["alpha", "beta"], ["alpha", "gamma"]

    first = diff_lines(old, new)
    second = diff_lines(list(old), list(new))
    diff_lines(old, ["alpha", "delta"])

    assert first == second
    assert [line.change for line in first] == [LineChange.CONTEXT, LineChange.REMOVED, LineChange.ADDED]
    assert len(matchers) == 2
