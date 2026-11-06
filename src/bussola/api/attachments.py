from pathlib import Path

from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool

from bussola.api.images import image_response
from bussola.api.schemas import AttachmentOut
from bussola.api.state import app_state
from bussola.attachments import MAX_ATTACHMENT_BYTES, attachments_dir, read_attachment, save_attachment

router = APIRouter(tags=["attachments"])


@router.post("/attachments", status_code=201)
async def upload_attachment(request: Request) -> AttachmentOut:
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_ATTACHMENT_BYTES:
            break
    return AttachmentOut(url=await run_in_threadpool(save_attachment, _directory(request), bytes(data)))


@router.get("/attachments/{name}")
def get_attachment(name: str, request: Request) -> Response:
    return image_response(*read_attachment(_directory(request), name))


def _directory(request: Request) -> Path:
    return attachments_dir(app_state(request).settings.data_dir)
