import pytest

from bussola.review.descriptions import MAX_SIDE_CHARACTERS, UnitInsight, unit_prompt
from bussola.storage.models import UnitSnapshot


def snapshot(base_text: str | None, head_text: str | None, *, kind: str = "function", name: str = "total", old_path: str | None = None) -> UnitSnapshot:
    return UnitSnapshot(
        revision_id=1,
        path="app.py",
        old_path=old_path,
        kind=kind,
        qualified_name=name,
        base_hash="b" if base_text is not None else None,
        head_hash="h" if head_text is not None else None,
        base_text=base_text,
        head_text=head_text,
        base_lines=[],
        head_lines=[],
    )


def test_a_new_unit_is_described_as_new() -> None:
    prompt = unit_prompt(snapshot(None, "def total():\n    return 1\n"))

    assert "<before>The unit did not exist before this change.</before>" in prompt
    assert "<after>\ndef total():\n    return 1\n\n</after>" in prompt


def test_a_removed_unit_is_described_as_removed() -> None:
    assert "<after>This change removes the unit.</after>" in unit_prompt(snapshot("def total(): ...", None))


def test_a_whole_file_and_a_rename_are_named() -> None:
    prompt = unit_prompt(snapshot("a", "b", kind="file", name="", old_path="old.py"))

    assert "Renamed from: old.py" in prompt
    assert "Name: (the whole file)" in prompt


def test_a_very_large_unit_is_clipped() -> None:
    prompt = unit_prompt(snapshot("x" * (MAX_SIDE_CHARACTERS + 10), "y"))

    assert "[... 10 more characters not shown]" in prompt
    assert "x" * (MAX_SIDE_CHARACTERS + 1) not in prompt


def test_the_impact_reason_is_kept_on_one_line() -> None:
    insight = UnitInsight.model_validate({"description": "  Text\n", "impact": "low", "impact_reason": "Only\n  a  rename.\n"})

    assert (insight.description, insight.impact_reason) == ("Text", "Only a rename.")


@pytest.mark.parametrize("field", ["description", "impact_reason"])
def test_an_empty_answer_is_refused(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        UnitInsight.model_validate({"description": "Text", "impact": "low", "impact_reason": "Reason"} | {field: ""})
