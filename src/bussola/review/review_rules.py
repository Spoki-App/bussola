from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

from bussola.git import GitRepo
from bussola.globs import matches_any
from bussola.review.descriptions import clipped_text

RULE_FILES = (".cursor/BUGBOT.md", "CLAUDE.md", ".claude/CLAUDE.md", "REVIEW.md", "AGENTS.md")
MAX_RULE_FILE_CHARACTERS = 20_000
MAX_RULES_CHARACTERS = 40_000


@dataclass(frozen=True)
class RuleFile:
    path: str
    text: str
    clipped: bool


def review_rules(repo: GitRepo, commit: str, changed: Iterable[str], ignore: tuple[str, ...]) -> tuple[RuleFile, ...]:
    blobs = {blob.path: blob for blob in repo.tree_blobs(commit) if blob.path.endswith(RULE_FILES) and not blob.is_symlink and not blob.is_submodule}
    candidates = (f"{folder}{name}" for folder in _folders(changed) for name in RULE_FILES)
    found = [blobs[path] for path in candidates if path in blobs and not matches_any(path, ignore)]
    if not found:
        return ()
    rules: list[RuleFile] = []
    room = MAX_RULES_CHARACTERS
    with repo.blob_reader() as reader:
        for blob in found:
            if room <= 0:
                break
            text = reader.read(blob.object_id).decode(errors="replace").strip()
            if not text:
                continue
            limit = min(room, MAX_RULE_FILE_CHARACTERS)
            rules.append(RuleFile(blob.path, clipped_text(text, limit), len(text) > limit))
            room -= min(len(text), limit)
    return tuple(rules)


def _folders(changed: Iterable[str]) -> list[str]:
    folders = {"", *(f"{parent}/" for path in changed for parent in PurePosixPath(path).parents if parent.name)}
    return sorted(folders, key=lambda folder: (folder.count("/"), folder))
