import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import PurePosixPath

PATH_SEPARATOR = "/"
GLOB_TOKENS = re.compile(r"\*\*/|\*\*|\*|\?|[^*?]+")
TOKEN_REGEX = {"**/": "(?:.*/)?", "**": ".*", "*": "[^/]*", "?": "[^/]"}


@lru_cache(maxsize=256)
def compile_glob(pattern: str) -> re.Pattern[str]:
    tokens: list[str] = GLOB_TOKENS.findall(pattern)
    regex = "".join(TOKEN_REGEX.get(token) or re.escape(token) for token in tokens)
    return re.compile(regex)


def matches_glob(path: str, pattern: str) -> bool:
    target = path if PATH_SEPARATOR in pattern else PurePosixPath(path).name
    return compile_glob(pattern.lstrip(PATH_SEPARATOR)).fullmatch(target) is not None


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(matches_glob(path, pattern) for pattern in patterns)
