import pytest

from bussola.handler.links import InvalidLinkError, ReviewLink, browser_path, parse_link

THREAD = "0123456789abcdef0123456789abcdef"


@pytest.mark.parametrize("url", ["bussola://", "bussola:///", "BUSSOLA://"])
def test_bare_scheme_opens_the_home_page(url: str) -> None:
    assert parse_link(url) is None
    assert browser_path(parse_link(url)) == "/"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("bussola://review?repo=acme/widgets&pr=7", ReviewLink("acme/widgets", 7)),
        ("bussola://review/?pr=7&repo=acme/widgets&utm_source=chat", ReviewLink("acme/widgets", 7)),
        ("bussola://review?repo=acme/widgets&pr=7&path=src/app.py&line=42", ReviewLink("acme/widgets", 7, path="src/app.py", line=42)),
        ("bussola://review?repo=acme/widgets&pr=7&path=docs/read%20me.md", ReviewLink("acme/widgets", 7, path="docs/read me.md")),
        (f"bussola://review?repo=acme/widgets&pr=7&thread={THREAD}", ReviewLink("acme/widgets", 7, thread=THREAD)),
        ("bussola://github.com/acme/widgets/pull/7", ReviewLink("acme/widgets", 7)),
        ("bussola://www.github.com/acme/my.widgets/pull/7/files?diff=split", ReviewLink("acme/my.widgets", 7)),
        ("bussola://github.com/acme/widgets/pull/7/files#discussion_r501", ReviewLink("acme/widgets", 7, comment=501)),
        ("bussola://github.com/acme/widgets/pull/7/files#r502", ReviewLink("acme/widgets", 7, comment=502)),
        ("bussola://github.com/acme/widgets/pull/7#issuecomment-9", ReviewLink("acme/widgets", 7)),
    ],
)
def test_supported_links(url: str, expected: ReviewLink) -> None:
    assert parse_link(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/acme/widgets/pull/7",
        "bussola:review?repo=acme/widgets&pr=7",
        "bussola://approve?repo=acme/widgets&pr=7",
        "bussola://review/approve?repo=acme/widgets&pr=7",
        "bussola://review?pr=7",
        "bussola://review?repo=acme&pr=7",
        "bussola://review?repo=acme/widgets/extra&pr=7",
        "bussola://review?repo=../..&pr=7",
        "bussola://review?repo=acme/widgets",
        "bussola://review?repo=acme/widgets&pr=0",
        "bussola://review?repo=acme/widgets&pr=-1",
        "bussola://review?repo=acme/widgets&pr=7x",
        "bussola://review?repo=acme/widgets&pr=7&pr=8",
        "bussola://review?repo=acme/widgets&pr=7&line=4",
        "bussola://review?repo=acme/widgets&pr=7&path=src/a.py&line=0",
        "bussola://review?repo=acme/widgets&pr=7&path=/etc/passwd",
        "bussola://review?repo=acme/widgets&pr=7&path=src/../../secret",
        "bussola://review?repo=acme/widgets&pr=7&path=src//a.py",
        "bussola://review?repo=acme/widgets&pr=7&path=src%5Ca.py",
        "bussola://review?repo=acme/widgets&pr=7&path=a%0Ab.py",
        "bussola://review?repo=acme/widgets&pr=7&thread=1%20OR%201",
        f"bussola://review?repo=acme/widgets&pr=7&thread={THREAD}%0A",
        "bussola://review?repo=acme/widgets%0A&pr=7",
        "bussola://review?repo=acme/widgets&pr=7%0A",
        "bussola://review?repo=acme/widgets&pr=1000000000",
        "bussola://review?repo=acme/widgets&pr=0000000001",
        "bussola://review?repo=acme/widgets&pr=" + "9" * 5000,
        "bussola://review?" + "&".join(f"x{index}=1" for index in range(40)),
        "bussola://github.com/acme/widgets/issues/7",
        "bussola://gitlab.com/acme/widgets/pull/7",
        "bussola://github.com.evil.example/acme/widgets/pull/7",
        "bussola://github.com/acme/widgets/pull/7abc",
        "bussola://github.com/acme/widgets/pull/1234567890",
        "bussola://github.com/acme/widgets/pull/0",
    ],
)
def test_invalid_links_are_refused(url: str) -> None:
    with pytest.raises(InvalidLinkError):
        parse_link(url)


def test_browser_path_mirrors_the_github_link_and_keeps_only_the_focus() -> None:
    assert browser_path(ReviewLink("acme/widgets", 7)) == "/github.com/acme/widgets/pull/7"
    assert browser_path(ReviewLink("acme/widgets", 7, path="src/a b.py", line=42)) == "/github.com/acme/widgets/pull/7?path=src%2Fa+b.py&line=42"
    assert browser_path(ReviewLink("acme/widgets", 7, thread=THREAD)) == f"/github.com/acme/widgets/pull/7?thread={THREAD}"
    assert browser_path(ReviewLink("acme/widgets", 7, comment=501)) == "/github.com/acme/widgets/pull/7?comment=501"
