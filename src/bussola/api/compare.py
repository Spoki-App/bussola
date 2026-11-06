from collections.abc import Iterable

from fastapi import APIRouter

from bussola.api.deps import ContextDep, resolve_revision, snapshot_of
from bussola.api.schemas import CodeRangeIn, CodeRangeOut, CompareIn, CompareOut, DiffRowOut, MoveOut
from bussola.errors import InvalidRequestError
from bussola.review.context import ReviewContext
from bussola.review.diffs import compare_lines
from bussola.review.moves import CodeRange, detect_moves, same_code
from bussola.review.rows import UnitLine, side_lines, side_path

router = APIRouter(tags=["compare"])


@router.get("/reviews/{review_id}/moves")
def list_moves(context: ContextDep, revision_id: int | None = None) -> list[MoveOut]:
    revision = resolve_revision(context, revision_id)
    moves = detect_moves(context.store.reviews.snapshots(revision.id))
    return [MoveOut(removed=_range_out(move.removed), added=_range_out(move.added), similarity=move.similarity, identical=move.identical) for move in moves]


@router.post("/reviews/{review_id}/compare")
def compare(context: ContextDep, body: CompareIn) -> CompareOut:
    left, right = _code_range(context, body.left), _code_range(context, body.right)
    old, new = left.lines(), right.lines()
    rows, unified = compare_lines(old, new, side_path(left.snapshot, left.side), side_path(right.snapshot, right.side))
    return CompareOut(
        left=_range_out(left),
        right=_range_out(right),
        identical=same_code(old, new),
        unified=unified,
        rows=[
            DiffRowOut(
                change=row.change,
                old_index=row.old_index,
                new_index=row.new_index,
                old_line=row.old_line,
                new_line=row.new_line,
                text=row.text,
                row_hash=None,
                approved=False,
                selection_id=None,
                placeholder=row.placeholder,
            )
            for row in rows
        ],
    )


def _code_range(context: ReviewContext, request: CodeRangeIn) -> CodeRange:
    snapshot = snapshot_of(context, request.unit_id)
    available = len(side_lines(snapshot, request.side))
    if request.line_offset >= available:
        raise InvalidRequestError(f"Unit {request.unit_id} has {available} lines on the {request.side.value} side")
    return CodeRange(snapshot, request.side, request.line_offset, min(request.line_offset + request.line_count, available) - 1)


def _range_out(code: CodeRange) -> CodeRangeOut:
    lines = code.lines()
    snapshot = code.snapshot
    return CodeRangeOut(
        unit_id=snapshot.id,
        path=side_path(snapshot, code.side),
        qualified_name=snapshot.qualified_name,
        kind=snapshot.kind,
        side=code.side,
        line_offset=code.start,
        line_count=code.count,
        first_line=_file_line(lines),
        last_line=_file_line(reversed(lines)),
    )


def _file_line(lines: Iterable[UnitLine]) -> int | None:
    return next((line.file_line for line in lines if line.file_line is not None), None)
