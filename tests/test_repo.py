import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EM_DASH = chr(0x2014)
TEXT_SUFFIXES = {".md", ".py", ".pyi", ".ts", ".tsx", ".js", ".css", ".html", ".json", ".toml", ".yml", ".yaml", ".sh", ".svg", ".ini", ""}
TOKEN = re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{60,}")
RELEASE_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$", re.MULTILINE)


def tracked_texts() -> dict[str, str]:
    listed = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    paths = [path for path in listed if Path(path).suffix in TEXT_SUFFIXES and (ROOT / path).is_file()]
    return {path: (ROOT / path).read_text(errors="ignore") for path in paths}


def test_no_em_dash_in_tracked_files() -> None:
    assert [path for path, text in tracked_texts().items() if EM_DASH in text] == []


def test_no_github_tokens_in_tracked_files() -> None:
    assert [path for path, text in tracked_texts().items() if TOKEN.search(text)] == []


def test_changelog_has_an_unreleased_section_and_the_latest_release_is_the_package_version() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    releases = RELEASE_HEADING.findall(changelog)

    assert "\n## [Unreleased]\n" in changelog
    assert releases[:1] in ([], [version])
