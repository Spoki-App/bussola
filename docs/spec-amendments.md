# Spec amendments

Changes to the original specification (`SPEC.md`, Italian). Where this file and the spec disagree, this file wins.

## A1. Range approval for `module` and `file` units

Functions, methods, classes and types are still approved as a whole. Code that is not inside one of them (`module` units) and whole-file units of unsupported languages (`file` units with text) can also be approved **one selection at a time**.

### Changed rows

For a unit with base text `B` and head text `H`, the line diff between `B` and `H` produces **changed rows**: lines added in head (`side = head`) and lines removed from base (`side = base`). Unchanged lines are never approved individually; they need no review.

Each changed row has a content identity:

```
row_hash = sha256(side, normalized line, previous line, next line, occurrence)
```

- `normalized line` follows section 5.3 (trailing spaces removed, CRLF to LF); leading indentation is kept, since inside a file it is meaningful.
- `previous line` and `next line` are the neighbouring lines on the same side of the diff (head lines for added rows, base lines for removed rows), so a row approved in one place does not count as approved somewhere else.
- `occurrence` separates rows that are identical in all of the above (0, 1, 2, ... in file order).

Anything that edits a row or its immediate neighbours produces a new identity, so the row needs review again. This errs on the side of asking for review.

### Approving a selection

- In the diff of a `module` or `file` unit the reviewer selects a range of rows (drag or shift-click on the gutter) and clicks "Approve selection" (or presses `a`).
- The API receives the selection as line ranges on each side; the backend resolves the changed rows inside them and stores one `row_approvals` record per row: `review_id`, `reviewer_id`, unit key, `side`, `row_hash`, `line_text`, `selection_id` (groups the rows approved together), `revision_id`, `created_at`, `revoked_at`.
- Revoking works per selection (all rows with the same `selection_id`) or per row. Like approvals, nothing is deleted.
- Approving the whole unit stays available and works as before (section 6.3).

### States

A new state `partial` is added between `changed` and `removed` in the table of section 6.2:

| State | Condition |
|---|---|
| `approved` | Whole-unit approval with the current `head_hash`, **or** every changed row is covered by an active row approval |
| `partial` | No whole-unit approval matches, and some but not all changed rows are covered by active row approvals |

- `partial` counts as "to review" (`todo` filter, progress bar, `n` shortcut).
- The diff marks approved rows, and the file tree counts only unapproved rows.
- "Since my last review" includes a `partial` unit when it has unapproved rows whose `row_hash` was not already present in the revision of the last session.

### API

```
POST   /reviews/{review_id}/approvals          {unit_id, head_range?: [start, end], base_range?: [start, end]}
DELETE /reviews/{review_id}/row-approvals/{selection_id}
```

`GET /reviews/{review_id}/units/{unit_id}/diff` returns, for each changed row, its `row_hash` and whether it is approved.

## A2. Publishing comments to GitHub

Sending review comments to a GitHub pull request is now in scope for v1. It is one-way (rtool to GitHub) and only happens on an explicit user action. Approvals are not published.

### Access

- A `GitHubAdapter` implements the `ForgeAdapter` interface of section 13 by running the `gh` CLI (`gh api ...`) through `subprocess` with an argument list. Authentication is whatever `gh auth login` already set up; rtool never sees or stores a token.
- If `gh` is missing or not authenticated, the UI shows how to fix it and the rest of the tool keeps working.
- `gh` calls are the only network access besides `git fetch` (amends section 15).

### Linking a review to a pull request

- The GitHub repository is derived from the review's remote URL (`git remote get-url <remote>`), validated as `owner/name`.
- rtool suggests the open pull request whose head and base branches match the review (`gh pr list --head ... --base ...`); the user can confirm it or enter a PR number.
- Table `forge_links`: `review_id`, `provider`, `repository`, `pr_number`, `created_at`.

### Sending

"Send to GitHub" collects the comments that have not been published yet (or were edited after publishing) and sends them as **one pull request review** at the PR head commit:

| rtool thread | On GitHub |
|---|---|
| Unit thread, line in the PR diff | Review comment on `path` and file line (`side` RIGHT for head, LEFT for base) |
| Unit thread, line outside the PR diff, or `outdated` | File comment (`subject_type: file`) quoting the line number and the anchored snippet |
| File thread | File comment |
| Review thread | Part of the review body |
| Reply in a thread already on GitHub | Reply to that review comment |

- The review is sent with event `COMMENT`, or left `PENDING` (draft) if the user ticks "keep as draft on GitHub".
- If the PR head SHA differs from the head SHA of the current revision, sending is blocked with a message asking to push or refresh, because line numbers would not match.
- Table `published_comments`: `comment_id`, `provider`, `remote_id`, `remote_url`, `published_at`, `published_body_hash`. A comment edited after publishing is updated on GitHub at the next send; a comment deleted locally is not deleted on GitHub.
- Resolving a thread is not propagated.

### API

```
GET    /reviews/{review_id}/forge              link status, detected PR candidates, gh availability
PUT    /reviews/{review_id}/forge              {pr_number}
POST   /reviews/{review_id}/forge/publish      {draft: bool} -> result for each comment (published, updated, failed with reason)
```

## A3. Choosing a repository folder from the UI

Browsers do not reveal the absolute path of a folder chosen with their native picker, so the home page has a folder browser served by rtool itself:

```
GET    /directories?path=                      folders inside path (default: the home directory), marking git repositories
GET    /directories/repositories               git repositories found under the home directory, marking those already added
```

- The repository scan walks the home directory breadth first, up to four levels deep. It skips hidden folders, dependency and build folders (`node_modules`, `vendor`, `dist`, `build`, `target` and similar) and macOS media and `Library` folders. It also looks inside repositories it found, since a repository can contain other independent repositories, but it does not follow symlinks, and it stops after five seconds or 500 results, reporting that the list is incomplete.

- Both return only folder names and paths and whether a folder contains `.git`; they never return file names or file contents.
- Both sit behind the same token and Host checks as the rest of the API.
- This is the one exception to section 11's rule about not reading the filesystem with paths from the input: only directory metadata is read.

## A4. Reviewing GitHub pull requests

For a repository whose remote (preferably `origin`) points to GitHub, rtool lists the open pull requests and turns any of them into a review.

```
GET    /repos/{repo_id}/pulls                  open pull requests (number, title, author, branches, draft, comments, unresolved threads) and the review already linked to each
POST   /repos/{repo_id}/pulls/{number}/review  fetch the pull request and start (or reuse) its review
POST   /repos/{repo_id}/pulls/sync             fetch every linked open pull request and refresh its review; mark closed or merged ones
```

- **Listing:** one GitHub GraphQL query through `gh api graphql` returns the open pull requests with their comment count (conversation comments plus review comments) and the number of review threads not resolved, which `gh pr list` cannot report.
- **Fetching:** `git fetch --no-tags <remote> +refs/pull/<n>/head:refs/rtool/pull/<n> +refs/heads/<base>:refs/remotes/<remote>/<base>`. The review compares `refs/rtool/pull/<n>` with `<remote>/<base>`, so the user's branches are never modified. The base branch name from GitHub is checked with `git check-ref-format --branch` before use.
- **Linking:** the review is linked to the pull request through `forge_links`, which also keeps its title, author, URL, state and last sync time. Publishing comments (A2) then needs no separate linking step.
- **Refresh:** on a pull request review, a refresh with `fetch` syncs that pull request instead of fetching the remote's default refspecs.
- **Network:** as in A2, GitHub is only contacted on an explicit user action.

## A5. Importing pull request comments from GitHub

This amends A2, where publishing was one-way: rtool now also reads the comments already on a linked pull request.

- **Source:** one GraphQL query through `gh api graphql` returns the pull request head, conversation comments, review summaries and review threads (path, line, start line, side, resolved state, comments). It runs when a pull request review is started, on **Sync reviews**, and on a refresh with fetch of a linked review.
- **Mapping:** a review thread becomes a unit thread on the same lines when the pull request head equals the reviewed head and the lines fall inside a changed unit; otherwise it becomes a file thread. Conversation comments and non-empty review summaries become review threads.
- **Identity:** every imported comment is recorded in `published_comments` with its GitHub id (`issue-<id>` and `review-<id>` for comments that cannot be replied to), so nothing is imported twice and nothing imported is sent back. A review sent from rtool is recorded as `review-<id>` for the same reason.
- **Authors:** the GitHub user running `gh` maps to the current reviewer; others become reviewers named after their login (`<login>@users.noreply.github.com`).
- **State:** the resolved state of imported threads follows GitHub at every import. Edits made on GitHub after import are not applied.

## Plan changes

- A1 is part of M2 (model, states, API) and M3 (selection UI).
- A2 is a new milestone **M4b** after M4 (2-3 days): `ForgeAdapter`, `GitHubAdapter` via `gh`, linking, publish and its tests. Tests run against a fake `gh` executable placed first on `PATH`, which records its arguments and returns canned JSON; no real network call is made.
- Section 1 "out of scope": GitHub integration is replaced by "anything on GitHub beyond publishing comments".
