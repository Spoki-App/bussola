import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any

from rtool.errors import InvalidRequestError
from rtool.forge.base import (
    Asset,
    Conversation,
    DiffSide,
    ForgeError,
    ForgeStatus,
    InlineComment,
    LineRanges,
    PullRequest,
    RemoteComment,
    RemoteNote,
    RemoteThread,
    ReviewSubmission,
    SubmittedReview,
)

GH = "gh"
PROVIDER = "github"
GH_TIMEOUT_SECONDS = 60
GH_ENV = {"GH_PROMPT_DISABLED": "1", "NO_COLOR": "1", "GH_NO_UPDATE_NOTIFIER": "1"}
PR_FIELDS = "number,title,url,headRefOid,headRefName,baseRefName,author,state,isDraft,updatedAt,body"
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

CONVERSATION_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  viewer { login }
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      headRefOid
      comments(first: 100) { nodes { databaseId author { login } body createdAt url } }
      reviews(first: 100) { nodes { databaseId author { login } body submittedAt url } }
      reviewThreads(first: 100) {
        nodes {
          id isResolved path line startLine diffSide
          comments(first: 100) { nodes { databaseId author { login } body createdAt url } }
        }
      }
    }
  }
}
"""
RESOLVE_THREAD_MUTATION = """
mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) { thread { isResolved } }
}
"""
UNRESOLVE_THREAD_MUTATION = """
mutation($threadId: ID!) {
  unresolveReviewThread(input: {threadId: $threadId}) { thread { isResolved } }
}
"""
ISSUE_COMMENT_PREFIX = "issue-"
ASSET_URL = re.compile(r"https://github\.com/(?:user-attachments/assets/[0-9a-f-]{36}|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/assets/\d+/[0-9a-f-]{36})")
MAX_ASSET_BYTES = 25 * 1024 * 1024
IMAGE_TYPE_PREFIX = "image/"
REVIEW_PREFIX = "review-"

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
        response = self._graphql(OPEN_PULLS_QUERY, owner=owner, name=name, limit=PR_LIST_LIMIT)
        try:
            nodes = response["data"]["repository"]["pullRequests"]["nodes"]
        except (KeyError, TypeError) as error:
            raise ForgeError(f"GitHub did not return the pull requests of {repository}") from error
        return [_pull_request(node) for node in nodes]

    def pull_request(self, repository: str, number: int) -> PullRequest:
        return _pull_request(self._json(["pr", "view", str(number), "--repo", _repo(repository), "--json", PR_FIELDS]))

    def diff_ranges(self, repository: str, number: int) -> dict[str, LineRanges]:
        files = self._paginated(f"repos/{_repo(repository)}/pulls/{number}/files")
        return {item["filename"]: parse_patch_ranges(item.get("patch") or "") for item in files}

    def submit_review(self, repository: str, number: int, submission: ReviewSubmission) -> SubmittedReview:
        payload: JsonObject = {
            "commit_id": submission.commit_id,
            "body": submission.body,
            "comments": [_inline_payload(item) for item in submission.comments],
        }
        if not submission.draft:
            payload["event"] = "COMMENT"
        review = self._json(["api", "--method", "POST", f"repos/{_repo(repository)}/pulls/{number}/reviews", "--input", "-"], payload)
        review_id = f"{REVIEW_PREFIX}{review['id']}" if "id" in review else None
        if not submission.comments:
            return SubmittedReview(review.get("html_url"), [], review_id)
        comments = self._paginated(f"repos/{_repo(repository)}/pulls/{number}/reviews/{review['id']}/comments")
        return SubmittedReview(review.get("html_url"), _match_comments(submission, comments), review_id)

    def create_file_comment(self, repository: str, number: int, commit_id: str, path: str, body: str) -> RemoteComment:
        payload = {"body": body, "commit_id": commit_id, "path": path, "subject_type": "file"}
        return _remote(self._json(["api", "--method", "POST", f"repos/{_repo(repository)}/pulls/{number}/comments", "--input", "-"], payload))

    def reply(self, repository: str, number: int, remote_id: str, body: str) -> RemoteComment:
        endpoint = f"repos/{_repo(repository)}/pulls/{number}/comments/{_numeric(remote_id)}/replies"
        return _remote(self._json(["api", "--method", "POST", endpoint, "--input", "-"], {"body": body}))

    def update_comment(self, repository: str, remote_id: str, body: str) -> None:
        self._json(["api", "--method", "PATCH", f"repos/{_repo(repository)}/pulls/comments/{_numeric(remote_id)}", "--input", "-"], {"body": body})

    def pull_request_conversation(self, repository: str, number: int) -> Conversation:
        owner, name = _repo(repository).split("/")
        response = self._graphql(CONVERSATION_QUERY, owner=owner, name=name, number=number)
        try:
            data = response["data"]
            pull = data["repository"]["pullRequest"]
        except (KeyError, TypeError) as error:
            raise ForgeError(f"GitHub did not return the comments of pull request #{number}") from error
        notes = [_note(item, ISSUE_COMMENT_PREFIX, "createdAt") for item in _nodes(pull.get("comments"))]
        notes += [_note(item, REVIEW_PREFIX, "submittedAt") for item in _nodes(pull.get("reviews")) if str(item.get("body") or "").strip()]
        threads = [_remote_thread(item) for item in _nodes(pull.get("reviewThreads"))]
        viewer: JsonObject = data.get("viewer") or {}
        return Conversation(str(viewer.get("login", "")), str(pull.get("headRefOid", "")), sorted(notes, key=lambda note: note.created_at), threads)

    def set_thread_resolved(self, thread_id: str, resolved: bool) -> None:
        mutation = RESOLVE_THREAD_MUTATION if resolved else UNRESOLVE_THREAD_MUTATION
        self._graphql(mutation, threadId=thread_id)

    def download_asset(self, url: str) -> Asset:
        if not ASSET_URL.fullmatch(url):
            raise InvalidRequestError("Only GitHub attachment links can be downloaded")
        token = self._run(["auth", "token"]).stdout.decode().strip()
        request = urllib.request.Request(url)
        request.add_unredirected_header("Authorization", f"Bearer {token}")
        try:
            with open_url(request, GH_TIMEOUT_SECONDS) as response:
                content_type: str = response.headers.get_content_type()
                data: bytes = response.read(MAX_ASSET_BYTES + 1)
        except (urllib.error.URLError, TimeoutError) as error:
            raise ForgeError(f"Could not download {url}: {error}") from error
        if len(data) > MAX_ASSET_BYTES or not content_type.startswith(IMAGE_TYPE_PREFIX):
            raise ForgeError(f"{url} is not an image rtool can show")
        return Asset(content_type, data)

    def _graphql(self, query: str, **variables: str | int) -> Any:
        args = ["api", "graphql", "-f", f"query={query}"]
        for name, value in variables.items():
            args += ["-F" if isinstance(value, int) else "-f", f"{name}={value}"]
        return self._json(args)

    def _paginated(self, endpoint: str) -> list[JsonObject]:
        pages: list[list[JsonObject]] = self._json(["api", "--paginate", "--slurp", endpoint])
        return [item for page in pages for item in page]

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


def open_url(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.build_opener().open(request, timeout=timeout)


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


def _nodes(connection: JsonObject | None) -> list[JsonObject]:
    return list((connection or {}).get("nodes") or [])


def _note(item: JsonObject, prefix: str, time_field: str) -> RemoteNote:
    return RemoteNote(
        remote_id=f"{prefix}{item['databaseId']}",
        author=_login(item.get("author")),
        body=str(item.get("body") or ""),
        created_at=str(item.get(time_field) or ""),
        url=str(item.get("url") or ""),
    )


def _remote_thread(item: JsonObject) -> RemoteThread:
    line = item.get("line")
    start = item.get("startLine")
    return RemoteThread(
        path=str(item.get("path") or ""),
        line=int(line) if line is not None else None,
        start_line=int(start) if start is not None else None,
        side=DiffSide.LEFT if item.get("diffSide") == DiffSide.LEFT else DiffSide.RIGHT,
        resolved=bool(item.get("isResolved", False)),
        comments=[_note(comment, "", "createdAt") for comment in _nodes(item.get("comments"))],
        remote_id=str(item.get("id") or ""),
    )


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
        unresolved_threads=sum(1 for thread in _nodes(item.get("reviewThreads")) if not thread.get("isResolved", False)),
        body=str(item.get("body") or ""),
    )


def _total(connection: JsonObject | None) -> int:
    return int(connection.get("totalCount", 0)) if connection else 0


def _comment_count(item: JsonObject) -> int:
    return _total(item.get("comments")) + sum(_total(thread.get("comments")) for thread in _nodes(item.get("reviewThreads")))


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
