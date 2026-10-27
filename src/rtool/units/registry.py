from pathlib import PurePosixPath

from rtool.units.extractors.base import Extractor
from rtool.units.extractors.javascript import JAVASCRIPT
from rtool.units.extractors.python import PythonExtractor
from rtool.units.extractors.typescript import TSX, TYPESCRIPT

PYTHON = PythonExtractor()

EXTRACTORS_BY_SUFFIX: dict[str, Extractor] = {
    ".py": PYTHON,
    ".pyi": PYTHON,
    ".ts": TYPESCRIPT,
    ".tsx": TSX,
    ".js": JAVASCRIPT,
    ".jsx": JAVASCRIPT,
    ".mjs": JAVASCRIPT,
    ".cjs": JAVASCRIPT,
}


def extractor_for(path: str) -> Extractor | None:
    return EXTRACTORS_BY_SUFFIX.get(PurePosixPath(path).suffix.lower())
