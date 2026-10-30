from bussola.units.normalize import content_hash, normalize


def test_normalize_strips_crlf_trailing_spaces_and_outer_blank_lines() -> None:
    assert normalize("\r\n  def f():   \r\n      return 1\r\n\r\n") == "def f():\n    return 1"


def test_indentation_change_of_whole_block_keeps_the_hash() -> None:
    assert content_hash("def f():\n    return 1") == content_hash("    def f():\n        return 1")


def test_comment_change_changes_the_hash() -> None:
    assert content_hash("x = 1  # one") != content_hash("x = 1  # two")


def test_inner_blank_lines_are_kept() -> None:
    assert content_hash("a\n\nb") != content_hash("a\nb")
