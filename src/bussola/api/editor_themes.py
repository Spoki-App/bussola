from fastapi import APIRouter

from bussola.api.schemas import EditorThemeOut
from bussola.editor_themes import editor_theme_content, find_editor_themes

router = APIRouter(tags=["editor-themes"])


@router.get("/editor-themes")
def list_editor_themes() -> list[EditorThemeOut]:
    return [EditorThemeOut(id=theme.id, label=theme.label, editor=theme.editor, extension=theme.extension, type=theme.type) for theme in find_editor_themes()]


@router.get("/editor-themes/{theme_id}")
def get_editor_theme(theme_id: str) -> dict[str, object]:
    return editor_theme_content(theme_id)
