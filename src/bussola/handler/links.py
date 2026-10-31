import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit

from bussola.errors import InvalidRequestError
from bussola.forge.pulls import parse_pull_request_url

SCHEME = "bussola"
BUSSOLA_MODULE = ("-P", "-m", "bussola")
HOME_PATH = "/"
REVIEW_HOST = "review"
GITHUB_HOSTS = ("github.com", "www.github.com")
ROOT_PATHS = ("", "/")
MAX_FIELDS = 16
MAX_PATH_LENGTH = 1024
NAME = r"[A-Za-z0-9_.-]{1,100}"
MAX_NUMBER = 999_999_999
DIGITS = re.compile(rf"[0-9]{{1,{len(str(MAX_NUMBER))}}}")
REPOSITORY = re.compile(rf"(?P<owner>{NAME})/(?P<name>{NAME})")
THREAD_ID = re.compile(r"[0-9a-f]{32}")
COMMENT_ID = re.compile(r"[1-9][0-9]{0,19}")
COMMENT_ANCHOR = re.compile(rf"(?:discussion_r|r|issuecomment-)(?P<comment>{COMMENT_ID.pattern})")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


class InvalidLinkError(InvalidRequestError):
    pass


@dataclass(frozen=True)
class ReviewLink:
    repository: str
    number: int
    path: str | None = None
    line: int | None = None
    thread: str | None = None
    comment: int | None = None


def parse_link(url: str) -> ReviewLink | None:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() != SCHEME:
        raise InvalidLinkError(f"Not a {SCHEME}:// link")
    host = parts.netloc.lower()
    if not host and parts.path in ROOT_PATHS:
        return None
    if host == REVIEW_HOST and parts.path in ROOT_PATHS:
        return _review_link(parts.query)
    if host in GITHUB_HOSTS:
        return _github_link(parts.path, parts.fragment)
    raise InvalidLinkError(f"Unsupported {SCHEME}:// link. Use {SCHEME}://review?repo=<owner>/<name>&pr=<number> or a GitHub pull request link.")


def browser_path(link: ReviewLink | None) -> str:
    if link is None:
        return HOME_PATH
    focus = {"path": link.path, "line": link.line, "thread": link.thread, "comment": link.comment}
    query = urlencode({key: value for key, value in focus.items() if value is not None})
    path = f"/github.com/{link.repository}/pull/{link.number}"
    return f"{path}?{query}" if query else path


def _review_link(query: str) -> ReviewLink:
    try:
        params = parse_qs(query, keep_blank_values=True, max_num_fields=MAX_FIELDS)
    except ValueError as error:
        raise InvalidLinkError("Too many link parameters") from error

    def single(name: str) -> str | None:
        values = params.get(name)
        if values is None:
            return None
        if len(values) != 1:
            raise InvalidLinkError(f"The {name} parameter is given more than once")
        return values[0]

    path = _file_path(single("path"))
    raw_line = single("line")
    line = None if raw_line is None else _number("line", raw_line)
    if line is not None and path is None:
        raise InvalidLinkError("The line parameter needs a path")
    return ReviewLink(
        repository=_repository(single("repo")),
        number=_number("pr", single("pr")),
        path=path,
        line=line,
        thread=_thread_id(single("thread")),
        comment=_optional_comment(single("comment")),
    )


def _github_link(path: str, fragment: str) -> ReviewLink:
    try:
        address = parse_pull_request_url(f"github.com{path}")
    except InvalidRequestError as error:
        raise InvalidLinkError(f"Not a GitHub pull request link. Expected {SCHEME}://github.com/<owner>/<name>/pull/<number>.") from error
    anchor = COMMENT_ANCHOR.fullmatch(fragment)
    return ReviewLink(
        repository=_repository(address.repository),
        number=_in_range("pr", address.number),
        comment=int(anchor["comment"]) if anchor else None,
    )


def _repository(value: str | None) -> str:
    match = REPOSITORY.fullmatch(value or "")
    if match is None or _only_dots(match["owner"]) or _only_dots(match["name"]):
        raise InvalidLinkError("The repo parameter must be <owner>/<name>")
    return match.group(0)


def _number(name: str, value: str | None) -> int:
    if value is None or DIGITS.fullmatch(value) is None:
        raise InvalidLinkError(f"The {name} parameter must be a positive number")
    return _in_range(name, int(value))


def _in_range(name: str, number: int) -> int:
    if not 0 < number <= MAX_NUMBER:
        raise InvalidLinkError(f"The {name} parameter must be a positive number up to {MAX_NUMBER}")
    return number


def _file_path(value: str | None) -> str | None:
    if value is None:
        return None
    segments = value.split("/")
    if len(value) > MAX_PATH_LENGTH or "\\" in value or CONTROL_CHARACTERS.search(value) or any(segment in ("", ".", "..") for segment in segments):
        raise InvalidLinkError("The path parameter must be a file path relative to the repository")
    return value


def _optional_comment(value: str | None) -> int | None:
    comment = _optional_match("comment", COMMENT_ID, value, "a GitHub comment id")
    return None if comment is None else int(comment)


def _thread_id(value: str | None) -> str | None:
    return _optional_match("thread", THREAD_ID, value, "a thread id")


def _optional_match(name: str, pattern: re.Pattern[str], value: str | None, expected: str) -> str | None:
    if value is not None and pattern.fullmatch(value) is None:
        raise InvalidLinkError(f"The {name} parameter must be {expected}")
    return value


def _only_dots(name: str) -> bool:
    return set(name) == {"."}
