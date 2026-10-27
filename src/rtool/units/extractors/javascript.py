import tree_sitter_javascript
from tree_sitter import Language

from rtool.units.extractors.ecmascript import EcmaScriptExtractor

JAVASCRIPT = EcmaScriptExtractor("javascript", Language(tree_sitter_javascript.language()))
