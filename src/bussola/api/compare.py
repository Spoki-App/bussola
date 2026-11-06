from fastapi import APIRouter

from bussola.api.deps import ContextDep, resolve_revision, snapshot_of
from bussola.api.schemas import CodeRangeIn, CodeRangeOut, CompareIn, CompareOut, MoveOut
from bussola.api.views import diff_row_out
from bussola.errors import InvalidRequestError
from bussola.review.context import ReviewContext
from bussola.review.diffs import compare_lines
from bussola.review.moves import CodeRange, detect_moves, same_code
from bussola.review.rows import side_lines, side_path

router = APIRouter(tags=["compare"])


@router.get("/reviews/{review_id}/moves")
def list_moves(context: ContextDep, revision_id: int | None = None) -> list[MoveOut]:
    revision = resolve_revision(context, revision_id)
    moves = detect_moves(context.store.reviews.snapshots(revision.id))
    return [MoveOut(removed=_range_out(move.removed), added=_range_out(move.added), similarity=move.similarity, identical=move.identical) for move in moves]


@router.post("/reviews/{review_id}/compare")
def compare(context: ContextDep, body: CompareIn) -> CompareOut:
    left, right = _code_range(context, body.left), _code_range(context, body.right)
    rows, unified = compare_lines(left.lines, right.lines, side_path(left.snapshot, left.side), side_path(right.snapshot, right.side))
    return CompareOut(
        left=_range_out(left),
        right=_range_out(right),
        identical=same_code(left.lines, right.lines),
        unified=unified,
        rows=[diff_row_out(row) for row in rows],
    )


def _code_range(context: ReviewContext, request: CodeRangeIn) -> CodeRange:
    snapshot = snapshot_of(context, request.unit_id)
    lines = side_lines(snapshot, request.side)
    if request.line_offset >= len(lines):
        raise InvalidRequestError(f"Unit {request.unit_id} has {len(lines)} lines on the {request.side.value} side")
    return CodeRange(snapshot, request.side, request.line_offset, lines[request.line_offset : request.line_offset + request.line_count])


def _range_out(code: CodeRange) -> CodeRangeOut:
    numbers = [line.file_line for line in code.lines if line.file_line is not None]
    return CodeRangeOut(
        unit_id=code.snapshot.id,
        path=side_path(code.snapshot, code.side),
        qualified_name=code.snapshot.qualified_name,
        kind=code.snapshot.kind,
        side=code.side,
        line_offset=code.start,
        line_count=len(code.lines),
        first_line=numbers[0] if numbers else None,
        last_line=numbers[-1] if numbers else None,
    )
