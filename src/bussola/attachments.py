import hashlib
import re
from pathlib import Path

from bussola.errors import InvalidRequestError, NotFoundError

ATTACHMENTS_DIR = "attachments"
ATTACHMENT_PATH = "/api/attachments/"
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MEDIA_TYPES = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
ATTACHMENT_NAME = re.compile(r"[0-9a-f]{64}\.(?P<extension>png|jpg|gif|webp)")
LOCAL_IMAGE = re.compile(r"!\[(?P<alt>[^\]]*)\]\(" + re.escape(ATTACHMENT_PATH) + ATTACHMENT_NAME.pattern + r"\)")


def attachments_dir(data_dir: Path) -> Path:
    return data_dir / ATTACHMENTS_DIR


def image_extension(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_attachment(directory: Path, data: bytes) -> str:
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise InvalidRequestError(f"Images can be at most {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB")
    extension = image_extension(data)
    if extension is None:
        raise InvalidRequestError("Only PNG, JPEG, GIF and WebP images can be attached")
    name = f"{hashlib.sha256(data).hexdigest()}.{extension}"
    path = directory / name
    if not path.exists():
        directory.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return f"{ATTACHMENT_PATH}{name}"


def read_attachment(directory: Path, name: str) -> tuple[bytes, str]:
    match = ATTACHMENT_NAME.fullmatch(name)
    path = directory / name
    if match is None or not path.is_file():
        raise NotFoundError(f"Attachment {name} not found")
    return path.read_bytes(), MEDIA_TYPES[match["extension"]]


def local_images_as_text(body: str) -> str:
    return LOCAL_IMAGE.sub(lambda match: f"*(image kept in bussola: {match['alt'] or 'image'})*", body)
