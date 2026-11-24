from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from bussola.git import BlobRef, GitRepo
from bussola.globs import matches_any
from bussola.review.descriptions import clipped_text
from bussola.storage.models import Revision

RULE_FILES = (".cursor/BUGBOT.md", "CLAUDE.md", ".claude/CLAUDE.md", "REVIEW.md", "AGENTS.md")
REVIEW_FILES = ("BUGBOT.md", "REVIEW.md")
MAX_RULE_FILE_CHARACTERS = 50_000
MAX_RULES_CHARACTERS = 120_000


class Skipped(StrEnum):
    ROOM = "room"
    IGNORED = "ignored"


@dataclass(frozen=True)
class RuleFile:
    path: str
    text: str = ""
    clipped: bool = False
    skipped: Skipped | None = None


def review_rules(
    repo: GitRepo, revision: Revision, changed: Iterable[str], ignore: tuple[str, ...], budget: int = MAX_RULES_CHARACTERS
) -> tuple[RuleFile, ...]:
    before, after = _rule_blobs(repo, revision.merge_base_sha), _rule_blobs(repo, revision.head_sha)
    candidates = dict.fromkeys(f"{folder}{name}" for folder in _folders(changed) for name in RULE_FILES)
    present = [path for path in candidates if path in before and path in after]
    ignored = [RuleFile(path, skipped=Skipped.IGNORED) for path in present if matches_any(path, ignore)]
    found = [before[path] for path in present if not matches_any(path, ignore)]
    texts = _texts(repo, found)
    limits = _limits(texts, budget)
    read = [
        RuleFile(path, clipped_text(text, limits[path]), len(text) > limits[path]) if path in limits else RuleFile(path, skipped=Skipped.ROOM)
        for path, text in texts.items()
    ]
    return (*read, *ignored)


def _texts(repo: GitRepo, blobs: list[BlobRef]) -> dict[str, str]:
    if not blobs:
        return {}
    with repo.blob_reader() as reader:
        return {blob.path: text for blob in blobs if (text := reader.read(blob.object_id).decode(errors="replace").strip())}


def _limits(texts: dict[str, str], budget: int) -> dict[str, int]:
    limits: dict[str, int] = {}
    room = budget
    for path in sorted(texts, key=_priority):
        if room <= 0:
            break
        limits[path] = min(len(texts[path]), room, MAX_RULE_FILE_CHARACTERS)
        room -= limits[path]
    return limits


def _priority(path: str) -> int:
    if PurePosixPath(path).name in REVIEW_FILES:
        return 0
    return 2 if path in RULE_FILES else 1


def _rule_blobs(repo: GitRepo, commit: str) -> dict[str, BlobRef]:
    return {blob.path: blob for blob in repo.tree_blobs(commit) if blob.path.endswith(RULE_FILES) and not blob.is_symlink and not blob.is_submodule}


def _folders(changed: Iterable[str]) -> list[str]:
    folders = {"", *(f"{parent}/" for path in changed for parent in PurePosixPath(path).parents if parent.name)}
    return sorted(folders, key=lambda folder: (folder.count("/"), folder))
