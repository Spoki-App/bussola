import pytest

from bussola.attachments import MAX_ATTACHMENT_BYTES
from tests.apiclient import ApiClient

PNG = b"\x89PNG\r\n\x1a\nimage"
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 "


def upload(api: ApiClient, data: bytes) -> tuple[int, dict[str, str]]:
    response = api.client.post("/api/attachments", content=data, headers={"Content-Type": "application/octet-stream"})
    return response.status_code, response.json()


def test_uploaded_images_are_served_from_the_local_copy(api: ApiClient) -> None:
    status, body = upload(api, PNG)

    image = api.client.get(body["url"])
    assert status == 201
    assert body["url"].startswith("/api/attachments/") and body["url"].endswith(".png")
    assert (image.status_code, image.content, image.headers["content-type"]) == (200, PNG, "image/png")
    assert "sandbox" in image.headers["content-security-policy"]


def test_the_same_image_is_stored_once(api: ApiClient) -> None:
    assert upload(api, WEBP)[1] == upload(api, WEBP)[1]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "Only PNG, JPEG, GIF and WebP images can be attached"),
        (PNG + b"0" * MAX_ATTACHMENT_BYTES, "Images can be at most 10 MB"),
    ],
)
def test_other_files_and_large_images_are_refused(api: ApiClient, data: bytes, message: str) -> None:
    assert upload(api, data) == (400, {"detail": message})


@pytest.mark.parametrize("name", ["missing.png", f"{'a' * 64}.png", "..%2Fbussola.db"])
def test_unknown_attachments_are_not_found(api: ApiClient, name: str) -> None:
    assert api.client.get(f"/api/attachments/{name}").status_code == 404
