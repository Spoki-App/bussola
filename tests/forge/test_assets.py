import urllib.request
from email.message import Message
from types import TracebackType
from typing import Self

import pytest

from rtool.forge import github
from tests.apiclient import ApiClient

ASSET = "https://github.com/user-attachments/assets/ad4619dd-3cdd-4568-a5e3-2fad4b1db525"
OTHER_ASSET = "https://github.com/acme/widgets/assets/42/bd4619dd-3cdd-4568-a5e3-2fad4b1db525"


class FakeResponse:
    def __init__(self, content_type: str, data: bytes) -> None:
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.data = data

    def read(self, limit: int) -> bytes:
        return self.data[:limit]

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: type[BaseException] | BaseException | TracebackType | None) -> None:
        return None


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[urllib.request.Request]:
    requests: list[urllib.request.Request] = []

    def fake_open(request: urllib.request.Request, _timeout: float) -> FakeResponse:
        requests.append(request)
        content_type = "text/html" if "0000" in request.full_url else "image/svg+xml"
        return FakeResponse(content_type, b"<svg/>")

    monkeypatch.setattr(github, "open_url", fake_open)
    return requests


@pytest.mark.usefixtures("fake_gh")
def test_github_attachments_are_served_with_the_gh_token(api: ApiClient, opened: list[urllib.request.Request]) -> None:
    response = api.client.get("/api/forge/asset", params={"url": ASSET})

    assert (response.status_code, response.content, response.headers["content-type"]) == (200, b"<svg/>", "image/svg+xml")
    assert "sandbox" in response.headers["content-security-policy"]
    assert opened[0].unredirected_hdrs == {"Authorization": "Bearer fake-token"}
    assert opened[0].headers == {}


@pytest.mark.usefixtures("fake_gh")
def test_attachments_are_downloaded_once(api: ApiClient, opened: list[urllib.request.Request]) -> None:
    api.client.get("/api/forge/asset", params={"url": OTHER_ASSET})
    api.client.get("/api/forge/asset", params={"url": OTHER_ASSET})

    assert len(opened) == 1


@pytest.mark.usefixtures("fake_gh")
def test_only_github_attachment_links_are_downloaded(api: ApiClient, opened: list[urllib.request.Request]) -> None:
    response = api.client.get("/api/forge/asset", params={"url": "https://example.com/user-attachments/assets/ad4619dd-3cdd-4568-a5e3-2fad4b1db525"})

    assert response.status_code == 400
    assert opened == []


@pytest.mark.usefixtures("fake_gh", "opened")
def test_attachments_that_are_not_images_are_refused(api: ApiClient) -> None:
    response = api.client.get("/api/forge/asset", params={"url": "https://github.com/user-attachments/assets/00000000-3cdd-4568-a5e3-2fad4b1db525"})

    assert response.status_code == 502
