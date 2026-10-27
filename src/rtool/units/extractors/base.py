from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from rtool.units.model import Unit, UnitKind
from rtool.units.normalize import UNIT_PLACEHOLDER, content_hash

DUPLICATE_SEPARATOR = "#"


class Extractor(Protocol):
    name: str
    version: int

    def extract(self, source: bytes) -> list[Unit] | None: ...


@dataclass(frozen=True)
class Span:
    kind: UnitKind
    qualified_name: str
    start_row: int
    end_row: int
    children: tuple["Span", ...] = field(default=())


@dataclass(frozen=True)
class SourceLines:
    lines: tuple[str, ...]

    @classmethod
    def from_bytes(cls, source: bytes) -> "SourceLines":
        return cls(tuple(source.decode("utf-8", errors="replace").split("\n")))

    def is_blank(self, row: int) -> bool:
        return not self.lines[row].strip()

    def text(self, rows: list[int | None]) -> str:
        return "\n".join(UNIT_PLACEHOLDER if row is None else self.lines[row] for row in rows)


def build_units(source: SourceLines, spans: list[Span]) -> list[Unit]:
    units: list[Unit] = []
    module_rows = carve(source, 0, len(source.lines) - 1, spans)
    if any(row is not None and not source.is_blank(row) for row in module_rows):
        units.append(_make_unit(source, UnitKind.MODULE, "", module_rows))
    for span in spans:
        _append_span_units(source, span, units)
    return with_unique_names(units)


def carve(source: SourceLines, start: int, end: int, holes: list[Span] | tuple[Span, ...]) -> list[int | None]:
    rows: list[int | None] = []
    row = start
    for hole_start, hole_end in _merged_intervals(holes):
        for kept in range(row, hole_start):
            _append_row(source, rows, kept)
        _append_placeholder(source, rows)
        row = hole_end + 1
    for kept in range(row, end + 1):
        _append_row(source, rows, kept)
    return rows


def with_unique_names(units: list[Unit]) -> list[Unit]:
    seen: Counter[tuple[UnitKind, str]] = Counter()
    renamed: list[Unit] = []
    for unit in units:
        key = (unit.kind, unit.qualified_name)
        seen[key] += 1
        if seen[key] == 1:
            renamed.append(unit)
        else:
            name = f"{unit.qualified_name}{DUPLICATE_SEPARATOR}{seen[key]}"
            renamed.append(Unit(unit.kind, name, unit.text, unit.content_hash, unit.line_numbers))
    return renamed


def _append_span_units(source: SourceLines, span: Span, units: list[Unit]) -> None:
    holes = [child for child in span.children if span.start_row < child.start_row <= child.end_row <= span.end_row]
    rows = carve(source, span.start_row, span.end_row, holes)
    units.append(_make_unit(source, span.kind, span.qualified_name, rows))
    for child in span.children:
        _append_span_units(source, child, units)


def _merged_intervals(holes: list[Span] | tuple[Span, ...]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for hole_start, hole_end in sorted((hole.start_row, hole.end_row) for hole in holes):
        if merged and hole_start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hole_end))
        else:
            merged.append((hole_start, hole_end))
    return merged


def _append_row(source: SourceLines, rows: list[int | None], row: int) -> None:
    if source.is_blank(row) and rows and rows[-1] is None:
        return
    rows.append(row)


def _append_placeholder(source: SourceLines, rows: list[int | None]) -> None:
    while rows and rows[-1] is not None and source.is_blank(rows[-1]):
        rows.pop()
    if not rows or rows[-1] is not None:
        rows.append(None)


def _make_unit(source: SourceLines, kind: UnitKind, qualified_name: str, rows: list[int | None]) -> Unit:
    text = source.text(rows)
    line_numbers = tuple(None if row is None else row + 1 for row in rows)
    return Unit(kind, qualified_name, text, content_hash(text), line_numbers)
