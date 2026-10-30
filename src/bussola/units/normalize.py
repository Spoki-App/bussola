import hashlib
import textwrap

UNIT_PLACEHOLDER = "⟨unit⟩"


def normalize(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    start = next((index for index, line in enumerate(lines) if line), len(lines))
    end = next((index for index in range(len(lines), 0, -1) if lines[index - 1]), start)
    return textwrap.dedent("\n".join(lines[start:end]))


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode()).hexdigest()
