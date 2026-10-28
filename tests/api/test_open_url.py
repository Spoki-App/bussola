import pytest

from tests.apiclient import ApiClient


def test_github_links_are_opened_in_the_default_browser(api: ApiClient) -> None:
    url = "https://github.com/acme/widgets/pull/7#discussion_r501"

    result = api.call("POST", "/open-url", body={"url": url})

    assert result == {"opened": True}
    assert api.opened_urls == [url]


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/acme/widgets",
        "https://evil.example/github.com",
        "https://github.com.evil.example/x",
        "file:///etc/passwd",
        "https://user@github.com/x",
    ],
)
def test_other_links_are_refused(api: ApiClient, url: str) -> None:
    api.call("POST", "/open-url", 400, {"url": url})

    assert api.opened_urls == []
