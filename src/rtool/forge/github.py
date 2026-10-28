import json
import os
import re
import shutil
import subprocess
from typing import Any

from rtool.forge.base import ForgeError, ForgeStatus, InlineComment, LineRanges, PullRequest, RemoteComment, ReviewSubmission, SubmittedReview

GH = "gh"
PROVIDER = "github"
GH_TIMEOUT_SECONDS = 60
GH_ENV = {"GH_PROMPT_DISABLED": "1", "NO_COLOR": "1", "GH_NO_UPDATE_NOTIFIER": "1"}
PR_FIELDS = "number,title,url,headRefOid,headRefName,baseRefName,author,state,isDraft,updatedAt"
PR_LIST_LIMIT = 100
OPEN_PULLS_QUERY = """
query($owner: String!, $name: String!, $limit: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: $limit, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes {
        number title url headRefOid headRefName baseRefName state isDraft updatedAt
        author { login }
        comments { totalCount }
        reviewThreads(first: 100) { nodes { isResolved comments { totalCount } } }
      }
    }
  }
}
"""
REPOSITORY_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
REMOTE_PATTERNS = (
    re.compile(r"^git@github\.com:(?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$"),
    re.compile(r"^(?:https?|ssh|git)://(?:[^@/]+@)?github\.com(?::\d+)?/(?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$"),
)
HUNK_HEADER = re.compile(r"^@@ -(?P<old>\d+)(?:,(?P<old_count>\d+))? \+(?P<new>\d+)(?:,(?P<new_count>\d+))? @@", re.MULTILINE)

type JsonObject = dict[str, Any]


class GitHubAdapter:
    provider: str = PROVIDER

    def status(self) -> ForgeStatus:
        if shutil.which(GH) is None:
            return ForgeStatus(available=False, authenticated=False, message="The GitHub CLI (gh) is not installed. Install it from https://cli.github.com.")
        result = self._run(["auth", "status"], check=False)
        if result.returncode != 0:
            return ForgeStatus(available=True, authenticated=False, message="gh is not logged in. Run `gh auth login` in a terminal.")
        return ForgeStatus(available=True, authenticated=True, message="gh is ready")

    def repository_for(self, remote_url: str) -> str | None:
        for pattern in REMOTE_PATTERNS:
            match = pattern.match(remote_url.strip())
            if match and REPOSITORY_NAME.fullmatch(match["repo"]):
                return match["repo"]
        return None

    def find_pull_requests(self, repository: str, head_branch: str, base_branch: str) -> list[PullRequest]:
        args = ["pr", "list", "--repo", _repo(repository), "--state", "open", "--head", head_branch, "--base", base_branch, "--json", PR_FIELDS]
        return [_pull_request(item) for item in self._json(args)]

    def open_pull_requests(self, repository: str) -> list[PullRequest]:
        owner, name = _repo(repository).split("/")
        args = ["api", "graphql", "-f", f"query={OPEN_PULLS_QUERY}", "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"limit={PR_LIST_LIMIT}"]
        response = self._json(args)
        try:
            nodes = response["data"]["repository"]["pullRequests"]["nodes"]
        except (KeyError, TypeError) as error:
            raise ForgeError(f"GitHub did not return the pull requests of {repository}") from error
        return [_pull_request(node) for node in nodes]

    def pull_request(self, repository: str, number: int) -> PullRequest:
        return _pull_request(self._json(["pr", "view", str(number), "--repo", _repo(repository), "--json", PR_FIELDS]))

    def diff_ranges(self, repository: str, number: int) -> dict[str, LineRanges]:
        pages = self._json(["api", "--paginate", "--slurp", f"repos/{_repo(repository)}/pulls/{number}/files"])
        return {item["filename"]: parse_patch_ranges(item.get("patch") or "") for page in pages for item in page}

    def submit_review(self, repository: str, number: int, submission: ReviewSubmission) -> SubmittedReview:
        payload: JsonObject = {
            "commit_id": submission.commit_id,
            "body": submission.body,
            "comments": [_inline_payload(item) for item in submission.comments],
        }
        if not submission.draft:
            payload["event"] = "COMMENT"
        review = self._json(["api", "--method", "POST", f"repos/{_repo(repository)}/pulls/{number}/reviews", "--input", "-"], payload)
        if not submission.comments:
            return SubmittedReview(review.get("html_url"), [])
        pages = self._json(["api", "--paginate", "--slurp", f"repos/{_repo(repository)}/pulls/{number}/reviews/{review['id']}/comments"])
        return SubmittedReview(review.get("html_url"), _match_comments(submission, [item for page in pages for item in page]))

    def create_file_comment(self, repository: str, number: int, commit_id: str, path: str, body: str) -> RemoteComment:
        payload = {"body": body, "commit_id": commit_id, "path": path, "subject_type": "file"}
        return _remote(self._json(["api", "--method", "POST", f"repos/{_repo(repository)}/pulls/{number}/comments", "--input", "-"], payload))

    def reply(self, repository: str, number: int, remote_id: str, body: str) -> RemoteComment:
        endpoint = f"repos/{_repo(repository)}/pulls/{number}/comments/{_numeric(remote_id)}/replies"
        return _remote(self._json(["api", "--method", "POST", endpoint, "--input", "-"], {"body": body}))

    def update_comment(self, repository: str, remote_id: str, body: str) -> None:
        self._json(["api", "--method", "PATCH", f"repos/{_repo(repository)}/pulls/comments/{_numeric(remote_id)}", "--input", "-"], {"body": body})

    def _json(self, args: list[str], payload: JsonObject | None = None) -> Any:
        result = self._run(args, payload=payload)
        try:
            return json.loads(result.stdout or b"null")
        except json.JSONDecodeError as error:
            raise ForgeError(f"Unexpected output from gh {args[0]}") from error

    def _run(self, args: list[str], *, payload: JsonObject | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
        executable = shutil.which(GH)
        if executable is None:
            raise ForgeError("The GitHub CLI (gh) is not installed")
        stdin = json.dumps(payload).encode() if payload is not None else None
        try:
            result = subprocess.run(
                [executable, *args], input=stdin, capture_output=True, check=False, timeout=GH_TIMEOUT_SECONDS, env={**os.environ, **GH_ENV}
            )
        except subprocess.TimeoutExpired as error:
            raise ForgeError("gh did not answer in time") from error
        if check and result.returncode != 0:
            raise ForgeError(result.stderr.decode(errors="replace").strip() or f"gh {args[0]} failed")
        return result


def parse_patch_ranges(patch: str) -> LineRanges:
    right: list[tuple[int, int]] = []
    left: list[tuple[int, int]] = []
    for match in HUNK_HEADER.finditer(patch):
        old_start, new_start = int(match["old"]), int(match["new"])
        old_count = int(match["old_count"]) if match["old_count"] is not None else 1
        new_count = int(match["new_count"]) if match["new_count"] is not None else 1
        if new_count:
            right.append((new_start, new_start + new_count - 1))
        if old_count:
            left.append((old_start, old_start + old_count - 1))
    return LineRanges(tuple(right), tuple(left))


def _inline_payload(item: InlineComment) -> JsonObject:
    payload: JsonObject = {"path": item.path, "line": item.line, "side": item.side.value, "body": item.body}
    if item.start_line is not None and item.start_line != item.line:
        payload.update(start_line=item.start_line, start_side=item.side.value)
    return payload


def _match_comments(submission: ReviewSubmission, remote: list[JsonObject]) -> list[RemoteComment]:
    available = list(remote)
    matched: list[RemoteComment] = []
    for item in submission.comments:
        found = next((candidate for candidate in available if candidate.get("path") == item.path and candidate.get("body") == item.body), None)
        if found is None:
            matched.append(RemoteComment(None, None))
            continue
        available.remove(found)
        matched.append(_remote(found))
    return matched


def _pull_request(item: JsonObject) -> PullRequest:
    return PullRequest(
        number=item["number"],
        title=item.get("title", ""),
        url=item.get("url", ""),
        head_sha=item["headRefOid"],
        head_ref=item.get("headRefName", ""),
        base_ref=item.get("baseRefName", ""),
        author=_login(item.get("author")),
        state=item.get("state", "OPEN"),
        is_draft=bool(item.get("isDraft", False)),
        updated_at=item.get("updatedAt", ""),
        comment_count=_comment_count(item),
        unresolved_threads=sum(1 for thread in _threads(item) if not thread.get("isResolved", False)),
    )


def _threads(item: JsonObject) -> list[JsonObject]:
    threads: JsonObject = item.get("reviewThreads") or {}
    return list(threads.get("nodes") or [])


def _total(connection: JsonObject | None) -> int:
    return int(connection.get("totalCount", 0)) if connection else 0


def _comment_count(item: JsonObject) -> int:
    return _total(item.get("comments")) + sum(_total(thread.get("comments")) for thread in _threads(item))


def _login(author: JsonObject | None) -> str:
    return str(author.get("login", "")) if author else ""


def _remote(item: JsonObject) -> RemoteComment:
    return RemoteComment(str(item["id"]) if "id" in item else None, item.get("html_url"))


def _repo(repository: str) -> str:
    if not REPOSITORY_NAME.fullmatch(repository):
        raise ForgeError(f"Not a GitHub repository name: {repository!r}")
    return repository


def _numeric(remote_id: str) -> str:
    if not remote_id.isdigit():
        raise ForgeError(f"Not a GitHub comment id: {remote_id!r}")
    return remote_id
