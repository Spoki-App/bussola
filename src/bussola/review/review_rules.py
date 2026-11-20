from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

from bussola.git import GitRepo
from bussola.globs import matches_any

RULE_FILES = (".cursor/BUGBOT.md", "CLAUDE.md", ".claude/CLAUDE.md", "REVIEW.md", "AGENTS.md")
MAX_RULE_FILE_CHARACTERS = 20_000
MAX_RULES_CHARACTERS = 40_000
CLIPPED_RULES = "\n[The rest of this file was too long to keep.]"


@dataclass(frozen=True)
class RuleFile:
    path: str
    text: str
    clipped: bool


def review_rules(repo: GitRepo, commit: str, changed: Iterable[str], ignore: tuple[str, ...]) -> list[RuleFile]:
    candidates = [f"{folder}{name}" for folder in _folders(changed) for name in RULE_FILES]
    order = {path: index for index, path in enumerate(candidates)}
    blobs = [blob for blob in repo.blobs_at(commit, candidates) if not blob.is_symlink and not matches_any(blob.path, ignore)]
    rules: list[RuleFile] = []
    room = MAX_RULES_CHARACTERS
    with repo.blob_reader() as reader:
        for blob in sorted(blobs, key=lambda blob: order[blob.path]):
            text = reader.read(blob.object_id).decode(errors="replace").strip()
            if not text:
                continue
            if room <= 0:
                break
            kept = text[: min(room, MAX_RULE_FILE_CHARACTERS)]
            room -= len(kept)
            rules.append(RuleFile(blob.path, kept if kept == text else kept + CLIPPED_RULES, kept != text))
    return rules


def _folders(changed: Iterable[str]) -> list[str]:
    folders = {"", *(f"{parent}/" for path in changed for parent in PurePosixPath(path).parents if parent.name)}
    return sorted(folders, key=lambda folder: (folder.count("/"), folder))
