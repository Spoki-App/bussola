from fastapi import Response

IMAGE_HEADERS = {
    "Cache-Control": "private, max-age=86400",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
}


def image_response(data: bytes, media_type: str) -> Response:
    return Response(data, media_type=media_type, headers=IMAGE_HEADERS)
