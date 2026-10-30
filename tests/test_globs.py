import pytest

from bussola.globs import matches_glob


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("app/migrations/0001_initial.py", "**/migrations/*.py", True),
        ("migrations/0001_initial.py", "**/migrations/*.py", True),
        ("app/migrations/sub/0001.py", "**/migrations/*.py", False),
        ("deep/dir/uv.lock", "*.lock", True),
        ("web/package-lock.json", "package-lock.json", True),
        ("src/app.py", "*.min.js", False),
        ("vendor/lib.min.js", "vendor/**", True),
        ("src/vendor/lib.js", "vendor/**", False),
    ],
)
def test_glob_matching(path: str, pattern: str, expected: bool) -> None:
    assert matches_glob(path, pattern) is expected
