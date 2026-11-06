from fastapi import APIRouter, Request, Response

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
    return AttachmentOut(url=save_attachment(attachments_dir(app_state(request).settings.data_dir), bytes(data)))


@router.get("/attachments/{name}")
def get_attachment(name: str, request: Request) -> Response:
    data, media_type = read_attachment(attachments_dir(app_state(request).settings.data_dir), name)
    return image_response(data, media_type)
