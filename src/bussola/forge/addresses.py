import re
from dataclasses import dataclass

from bussola.errors import InvalidRequestError

PULL_URL = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(?P<number>\d{1,18})(?:[/?#].*)?$")


@dataclass(frozen=True)
class PullRequestAddress:
    repository: str
    number: int


def parse_pull_request_url(url: str) -> PullRequestAddress:
    match = PULL_URL.match(url.strip())
    if match is None:
        raise InvalidRequestError("Not a GitHub pull request link. Expected https://github.com/<owner>/<repository>/pull/<number>.")
    return PullRequestAddress(match["repository"], int(match["number"]))
