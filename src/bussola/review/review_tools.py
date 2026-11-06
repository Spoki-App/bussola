import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from bussola.ai.base import Cancellation
from bussola.ai.tools import AiTool, Toolbox, ToolError
from bussola.git import GitError, GitRepo
from bussola.globs import matches_any
from bussola.navigation.navigator import Click, Navigation, Navigator, Origin, Target
from bussola.navigation.positions import byte_to_utf16, source_lines
from bussola.review.descriptions import UNIT_NAMES, unit_prompt
from bussola.review.rows import Side, side_commit
from bussola.storage.models import Revision, UnitSnapshot

MAX_TOOL_CALLS = 40
MAX_READ_LINES = 300
MAX_TARGETS = 50
MAX_SEARCH_RESULTS = 50
INDEX_WAIT_SECONDS = 120.0
INDEX_POLL_SECONDS = 0.5
FIND_USAGES = (
    "Every place that uses a name, across the whole repository, like Cmd+click on a definition in an editor. "
    "Give the line of the definition or of any use. Returns path:line and the line of each use."
)
SIDES = {"after": Side.HEAD, "before": Side.BASE}
IDENTIFIER_BYTE = rb"[A-Za-z0-9_$]"

type SideName = Literal["after", "before"]


class Location(BaseModel):
    path: str = Field(description="File path from the repository root, as shown in the pull request")
    side: SideName = Field(description="after for the new version, before for the version the pull request starts from")
    line: int = Field(description="Line number in the file")
    name: str = Field(description="The name on that line, such as a function, method, class or variable")


class FileRange(BaseModel):
    path: str = Field(description="File path from the repository root")
    side: SideName = Field(description="after for the new version, before for the version the pull request starts from")
    start_line: int = Field(description="First line to read")
    end_line: int = Field(description=f"Last line to read, at most {MAX_READ_LINES} lines after start_line")


class TextSearch(BaseModel):
    text: str = Field(description="Exact text to look for, such as a name or a string literal")
    side: SideName = Field(description="after for the new version, before for the version the pull request starts from")


class UnitName(BaseModel):
    unit: str = Field(description="A unit exactly as the list of changed units names it, such as app/billing.py::total")


def unit_label(snapshot: UnitSnapshot) -> str:
    return label_of(snapshot.path, snapshot.kind, snapshot.qualified_name)


def label_of(path: str | None, kind: str | None, qualified_name: str | None) -> str:
    return f"{path}::{qualified_name or UNIT_NAMES.get(kind or '', kind or '')}"


@dataclass(frozen=True)
class ReviewTools:
    repo: GitRepo
    revision: Revision
    snapshots: list[UnitSnapshot]
    navigator: Navigator
    ignore: tuple[str, ...]
    cancellation: Cancellation

    def toolbox(self, on_call: Callable[[], None] | None = None) -> Toolbox:
        return Toolbox(
            [
                AiTool(
                    "find_definition",
                    "Where a name used on a line is defined, like Cmd+click on a use in an editor. Returns path:line and the line of each definition.",
                    Location,
                    self.find_definition,
                ),
                AiTool(
                    "find_usages",
                    FIND_USAGES,
                    Location,
                    self.find_usages,
                ),
                AiTool("read_file", f"Lines of any file of the repository, numbered, at most {MAX_READ_LINES} at a time.", FileRange, self.read_file),
                AiTool("search", f"Lines of the repository that contain an exact text, at most {MAX_SEARCH_RESULTS}.", TextSearch, self.search),
                AiTool("unit_diff", "One changed unit of the pull request before and after the change, with line numbers.", UnitName, self.unit_diff),
            ],
            MAX_TOOL_CALLS,
            on_call,
        )

    def prepare(self) -> None:
        for side in Side:
            self.navigator.prepare(self.repo, side_commit(self.revision, side), self.ignore)

    def find_definition(self, location: Location) -> str:
        found = self._navigate(location)
        if found.origin == Origin.DEFINITION:
            return f"{location.path}:{location.line} is where {found.symbol} is defined."
        if (documentation := found.documentation) is not None:
            summary = f"{location.name} is {documentation.qualified_name} from the external package {documentation.package}, not defined in this repository."
            return "\n\n".join(part for part in (summary, documentation.signature, documentation.docstring) if part)
        return self._targets(found.targets, f"No definition of {location.name} was found.")

    def find_usages(self, location: Location) -> str:
        found = self._navigate(location)
        if found.origin == Origin.REFERENCE:
            definition = found.targets[0] if found.targets else None
            if definition is None:
                return f"No definition of {location.name} was found, so its usages are unknown. Try search."
            found = self._wait(SIDES[location.side], Click(definition.path, definition.line, definition.column))
        return self._targets(found.targets, f"No usages of {location.name} were found.")

    def read_file(self, request: FileRange) -> str:
        if request.end_line < request.start_line:
            raise ToolError("end_line must not be before start_line")
        lines = self._lines(request.path, SIDES[request.side])
        start = max(request.start_line, 1)
        if start > len(lines):
            raise ToolError(f"{request.path} has {len(lines)} lines on the {request.side} side")
        end = min(request.end_line, start + MAX_READ_LINES - 1, len(lines))
        return "\n".join(f"{number}: {lines[number - 1].decode(errors='replace')}" for number in range(start, end + 1))

    def search(self, request: TextSearch) -> str:
        if not request.text.strip():
            raise ToolError("Give some text to look for")
        try:
            found = self.repo.grep(side_commit(self.revision, SIDES[request.side]), request.text, self._visible, MAX_SEARCH_RESULTS)
        except GitError as error:
            raise ToolError(f"The search failed: {error.stderr.strip() or error}") from error
        if not found.matches:
            return f"Nothing contains {request.text!r}."
        shown = [f"{match.path}:{match.line}: {match.text.strip()}" for match in found.matches]
        return "\n".join(shown + ([f"Only the first {MAX_SEARCH_RESULTS} are shown; search for something more specific."] if found.more else []))

    def unit_diff(self, request: UnitName) -> str:
        snapshot = next((snapshot for snapshot in self.snapshots if unit_label(snapshot) == request.unit), None)
        if snapshot is None:
            raise ToolError(f"No changed unit is named {request.unit}. Use a name from the list of changed units.")
        return unit_prompt(snapshot, numbered=True)

    def _navigate(self, location: Location) -> Navigation:
        side = SIDES[location.side]
        lines = self._lines(location.path, side)
        if not 1 <= location.line <= len(lines):
            raise ToolError(f"{location.path} has {len(lines)} lines on the {location.side} side")
        line = lines[location.line - 1]
        found = re.search(rb"(?<!" + IDENTIFIER_BYTE + rb")" + re.escape(location.name.encode()) + rb"(?!" + IDENTIFIER_BYTE + rb")", line)
        if found is None:
            raise ToolError(f"Line {location.line} of {location.path} does not contain {location.name}")
        return self._wait(side, Click(location.path, location.line, byte_to_utf16(line, found.start())))

    def _wait(self, side: Side, click: Click) -> Navigation:
        commit = side_commit(self.revision, side)
        found = self.navigator.navigate(self.repo, commit, self.ignore, click)
        waited = 0.0
        while not found.ready:
            if waited >= INDEX_WAIT_SECONDS:
                raise ToolError("The code index is still being built. Use search or read_file instead.")
            self.cancellation.sleep(INDEX_POLL_SECONDS)
            waited += INDEX_POLL_SECONDS
            if self.navigator.prepare(self.repo, commit, self.ignore):
                found = self.navigator.navigate(self.repo, commit, self.ignore, click)
        return found

    def _lines(self, path: str, side: Side) -> list[bytes]:
        if not self._visible(path):
            raise ToolError(f"{path} is excluded from reviews in this repository")
        data = self.repo.file_at(side_commit(self.revision, side), path)
        if data is None:
            raise ToolError(f"{path} does not exist on the {'before' if side == Side.BASE else 'after'} side")
        lines = source_lines(data)
        return lines[:-1] if len(lines) > 1 and not lines[-1] else lines

    def _targets(self, targets: tuple[Target, ...], empty: str) -> str:
        visible = [target for target in targets if self._visible(target.path)]
        if not visible:
            return empty
        shown = [f"{target.path}:{target.line}: {target.preview}" for target in visible[:MAX_TARGETS]]
        more = len(visible) - len(shown)
        return "\n".join(shown + ([f"... and {more} more"] if more else []))

    def _visible(self, path: str) -> bool:
        return not matches_any(path, self.ignore)
