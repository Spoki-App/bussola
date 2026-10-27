import tree_sitter_typescript
from tree_sitter import Language

from rtool.units.extractors.ecmascript import EcmaScriptExtractor

TYPESCRIPT = EcmaScriptExtractor("typescript", Language(tree_sitter_typescript.language_typescript()))
TSX = EcmaScriptExtractor("tsx", Language(tree_sitter_typescript.language_tsx()))
