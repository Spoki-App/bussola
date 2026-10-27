from dataclasses import dataclass
from enum import StrEnum


class UnitKind(StrEnum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    TYPE = "type"
    MODULE = "module"
    FILE = "file"


@dataclass(frozen=True)
class UnitKey:
    path: str
    kind: UnitKind
    qualified_name: str

    def __str__(self) -> str:
        return f"{self.path}::{self.qualified_name}" if self.qualified_name else self.path


@dataclass(frozen=True)
class Unit:
    kind: UnitKind
    qualified_name: str
    text: str | None
    content_hash: str
    line_numbers: tuple[int | None, ...]

    @property
    def start_line(self) -> int | None:
        return next((line for line in self.line_numbers if line is not None), None)

    @property
    def end_line(self) -> int | None:
        return next((line for line in reversed(self.line_numbers) if line is not None), None)
