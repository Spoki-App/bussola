from bussola.units.model import Unit, UnitKind
from bussola.units.normalize import content_hash

FILE_UNIT_NAME = ""


def file_unit(source: bytes) -> Unit:
    text = source.decode("utf-8", errors="replace")
    line_count = len(text.split("\n"))
    return Unit(UnitKind.FILE, FILE_UNIT_NAME, text, content_hash(text), tuple(range(1, line_count + 1)))


def binary_unit(object_id: str) -> Unit:
    return Unit(UnitKind.FILE, FILE_UNIT_NAME, None, object_id, ())


def submodule_unit(commit_id: str) -> Unit:
    text = f"Subproject commit {commit_id}"
    return Unit(UnitKind.FILE, FILE_UNIT_NAME, text, content_hash(text), (1,))
