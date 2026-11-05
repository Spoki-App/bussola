import re
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
from bussola.review.rows import Side
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
GREP_LINE = re.compile(r"^[^:]+:(?P<path>.*?):(?P<line>\d+):(?P<text>.*)$")

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
    return f"{snapshot.path}::{snapshot.qualified_name or UNIT_NAMES.get(snapshot.kind, snapshot.kind)}"


@dataclass(frozen=True)
class ReviewTools:
    repo: GitRepo
    revision: Revision
    snapshots: list[UnitSnapshot]
    navigator: Navigator
    ignore: tuple[str, ...]
    cancellation: Cancellation

    def toolbox(self) -> Toolbox:
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
        )

    def prepare(self) -> None:
        for side in Side:
            self.navigator.prepare(self.repo, self._commit(side), self.ignore)

    def find_definition(self, location: Location) -> str:
        found = self._navigate(location)
        if found.origin == Origin.DEFINITION:
            return f"{location.path}:{location.line} is where {found.symbol} is defined."
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
        lines = self._file(request.path, SIDES[request.side]).splitlines()
        start = max(request.start_line, 1)
        end = min(request.end_line, start + MAX_READ_LINES - 1, len(lines))
        if start > len(lines):
            raise ToolError(f"{request.path} has {len(lines)} lines on the {request.side} side")
        return "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))

    def search(self, request: TextSearch) -> str:
        if not request.text.strip():
            raise ToolError("Give some text to look for")
        try:
            output = self.repo.run("grep", "-n", "-I", "-F", "-e", request.text, self._commit(SIDES[request.side]), "--")
        except GitError:
            return f"Nothing contains {request.text!r}."
        found = [match for line in output.decode(errors="replace").splitlines() if (match := GREP_LINE.match(line)) and self._visible(match["path"])]
        shown = [f"{match['path']}:{match['line']}: {match['text'].strip()}" for match in found[:MAX_SEARCH_RESULTS]]
        more = len(found) - len(shown)
        return "\n".join(shown + ([f"... and {more} more"] if more else [])) or f"Nothing contains {request.text!r}."

    def unit_diff(self, request: UnitName) -> str:
        snapshot = next((snapshot for snapshot in self.snapshots if unit_label(snapshot) == request.unit), None)
        if snapshot is None:
            raise ToolError(f"No changed unit is named {request.unit}. Use a name from the list of changed units.")
        return unit_prompt(snapshot, numbered=True)

    def _navigate(self, location: Location) -> Navigation:
        side = SIDES[location.side]
        lines = source_lines(self._file(location.path, side).encode())
        if not 1 <= location.line <= len(lines):
            raise ToolError(f"{location.path} has {len(lines)} lines on the {location.side} side")
        line = lines[location.line - 1]
        start = line.find(location.name.encode())
        if start < 0:
            raise ToolError(f"Line {location.line} of {location.path} does not contain {location.name}")
        return self._wait(side, Click(location.path, location.line, byte_to_utf16(line, start)))

    def _wait(self, side: Side, click: Click) -> Navigation:
        waited = 0.0
        while True:
            found = self.navigator.navigate(self.repo, self._commit(side), self.ignore, click)
            if found.ready:
                return found
            if waited >= INDEX_WAIT_SECONDS:
                raise ToolError("The code index is still being built. Use search or read_file instead.")
            self.cancellation.sleep(INDEX_POLL_SECONDS)
            waited += INDEX_POLL_SECONDS

    def _file(self, path: str, side: Side) -> str:
        if not self._visible(path):
            raise ToolError(f"{path} is excluded from reviews in this repository")
        data = self.repo.file_at(self._commit(side), path)
        if data is None:
            raise ToolError(f"{path} does not exist on the {'before' if side == Side.BASE else 'after'} side")
        return data.decode(errors="replace")

    def _targets(self, targets: tuple[Target, ...], empty: str) -> str:
        visible = [target for target in targets if self._visible(target.path)]
        if not visible:
            return empty
        shown = [f"{target.path}:{target.line}: {target.preview}" for target in visible[:MAX_TARGETS]]
        more = len(visible) - len(shown)
        return "\n".join(shown + ([f"... and {more} more"] if more else []))

    def _visible(self, path: str) -> bool:
        return not matches_any(path, self.ignore)

    def _commit(self, side: Side) -> str:
        return self.revision.merge_base_sha if side == Side.BASE else self.revision.head_sha
