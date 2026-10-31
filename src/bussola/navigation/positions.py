UTF16 = "utf-16-le"
UTF16_UNIT_BYTES = 2
PREVIEW_CHARS = 200


def source_lines(source: bytes) -> list[bytes]:
    return [line.removesuffix(b"\r") for line in source.split(b"\n")]


def utf16_to_byte(line: bytes, column: int) -> int:
    text = line.decode(errors="replace")
    prefix = text.encode(UTF16, errors="surrogatepass")[: column * UTF16_UNIT_BYTES].decode(UTF16, errors="ignore")
    return len(prefix.encode(errors="replace"))


def byte_to_utf16(line: bytes, column: int) -> int:
    return len(line[:column].decode(errors="replace").encode(UTF16, errors="surrogatepass")) // UTF16_UNIT_BYTES


def preview(line: bytes) -> str:
    return line.decode(errors="replace").strip()[:PREVIEW_CHARS]
