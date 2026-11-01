import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from bussola.ai.base import AiProvider, Cancellation
from bussola.ai.runner import AiCache, AiRunner, AiTask
from bussola.errors import InvalidRequestError
from bussola.review.keys import KeyTuple, key_of
from bussola.review.rows import is_binary
from bussola.storage.models import UnitDescription, UnitSnapshot


class Impact(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


MAX_SIDE_CHARACTERS = 40_000
UNIT_NAMES = {"file": "file", "module": "module-level code"}


class UnitInsight(BaseModel):
    description: str = Field(min_length=1)
    impact: Impact
    impact_reason: str = Field(min_length=1)

    @field_validator("description")
    @classmethod
    def _trimmed(cls, description: str) -> str:
        return description.strip()

    @field_validator("impact_reason")
    @classmethod
    def _one_line(cls, reason: str) -> str:
        return " ".join(reason.split())


DESCRIBE_UNIT = AiTask(
    name="describe_unit",
    version=1,
    system=(
        "You help a code reviewer understand one unit of a change: a function, method, class, type, module-level code or a whole file. "
        "You get the unit before and after the change. Answer only with JSON that matches the given schema.\n\n"
        "description: GitHub-flavored Markdown for the reviewer, short and concrete. Start with what the unit does, "
        "then explain what this change does to it and why it matters. Mention behaviour changes, edge cases and risks. "
        "Do not repeat the code line by line and do not add a title.\n\n"
        "impact: how much the change can affect the behaviour of the program and deserves the reviewer's attention. "
        "low: no behaviour change or a trivial one, such as formatting, comments, renames, logging or tests. "
        "medium: a contained behaviour change with limited reach. "
        "high: a change to core logic, data, security, money, concurrency, public interfaces or anything that is hard to undo.\n\n"
        "impact_reason: one short sentence that justifies the impact."
    ),
    output=UnitInsight,
)


@dataclass(frozen=True)
class StoredDescription:
    description: UnitDescription
    outdated: bool


def change_hash(snapshot: UnitSnapshot) -> str:
    return hashlib.sha256(json.dumps([snapshot.base_hash, snapshot.head_hash]).encode()).hexdigest()


def describable(snapshot: UnitSnapshot) -> bool:
    return not is_binary(snapshot)


def stored_descriptions(snapshots: Iterable[UnitSnapshot], descriptions: Iterable[UnitDescription]) -> dict[int, StoredDescription]:
    latest: dict[KeyTuple, UnitDescription] = {}
    exact: dict[tuple[KeyTuple, str], UnitDescription] = {}
    for description in descriptions:
        key = (description.path, description.kind, description.qualified_name)
        latest[key] = description
        exact[(key, description.change_hash)] = description
    found: dict[int, StoredDescription] = {}
    for snapshot in snapshots:
        current = exact.get((key_of(snapshot), change_hash(snapshot)))
        if current is not None:
            found[snapshot.id] = StoredDescription(current, outdated=False)
        elif (previous := latest.get(key_of(snapshot))) is not None:
            found[snapshot.id] = StoredDescription(previous, outdated=True)
    return found


def describe_unit(snapshot: UnitSnapshot, provider: AiProvider, cache: AiCache | None, cancellation: Cancellation, *, regenerate: bool = False) -> UnitInsight:
    if not describable(snapshot):
        raise InvalidRequestError("Binary files cannot be described")
    prompt = unit_prompt(snapshot)
    content_hash = hashlib.sha256(prompt.encode()).hexdigest()
    return AiRunner(provider, cache).run(DESCRIBE_UNIT, prompt, cancellation, content_hash=content_hash, refresh=regenerate)


def unit_prompt(snapshot: UnitSnapshot) -> str:
    name = snapshot.qualified_name or f"(the whole {UNIT_NAMES.get(snapshot.kind, snapshot.kind)})"
    lines = [f"Path: {snapshot.path}"]
    if snapshot.old_path and snapshot.old_path != snapshot.path:
        lines.append(f"Renamed from: {snapshot.old_path}")
    lines += [f"Kind: {snapshot.kind}", f"Name: {name}", ""]
    lines += _side("before", snapshot.base_text, "The unit did not exist before this change.")
    lines += _side("after", snapshot.head_text, "This change removes the unit.")
    return "\n".join(lines)


def _side(tag: str, text: str | None, missing: str) -> list[str]:
    if text is None:
        return [f"<{tag}>{missing}</{tag}>", ""]
    return [f"<{tag}>", _clipped(text), f"</{tag}>", ""]


def _clipped(text: str) -> str:
    if len(text) <= MAX_SIDE_CHARACTERS:
        return text
    return f"{text[:MAX_SIDE_CHARACTERS]}\n[... {len(text) - MAX_SIDE_CHARACTERS} more characters not shown]"
