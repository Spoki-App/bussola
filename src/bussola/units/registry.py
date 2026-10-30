from pathlib import PurePosixPath

from bussola.units.extractors.base import Extractor
from bussola.units.extractors.go import GoExtractor
from bussola.units.extractors.javascript import JAVASCRIPT
from bussola.units.extractors.python import PythonExtractor
from bussola.units.extractors.typescript import TSX, TYPESCRIPT

PYTHON = PythonExtractor()
GO = GoExtractor()

EXTRACTORS_BY_SUFFIX: dict[str, Extractor] = {
    ".py": PYTHON,
    ".pyi": PYTHON,
    ".ts": TYPESCRIPT,
    ".tsx": TSX,
    ".js": JAVASCRIPT,
    ".jsx": JAVASCRIPT,
    ".mjs": JAVASCRIPT,
    ".cjs": JAVASCRIPT,
    ".go": GO,
}


def extractor_for(path: str) -> Extractor | None:
    return EXTRACTORS_BY_SUFFIX.get(PurePosixPath(path).suffix.lower())
