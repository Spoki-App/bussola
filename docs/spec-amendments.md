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

- The review is sent with event `COMMENT` (sending as a pending draft was dropped in A7).
- If the PR head SHA differs from the head SHA of the current revision, sending is blocked with a message asking to push or refresh, because line numbers would not match.
- Table `published_comments`: `comment_id`, `provider`, `remote_id`, `remote_url`, `published_at`, `published_body_hash`. A comment edited after publishing is updated on GitHub at the next send; a comment deleted locally is not deleted on GitHub.
- Resolving a thread is not propagated (changed by A6).

### API

```
GET    /reviews/{review_id}/forge              link status, detected PR candidates, gh availability
PUT    /reviews/{review_id}/forge              {pr_number}
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
- **State:** the resolved state of imported threads follows GitHub at every import. Edits made on GitHub after import are not applied (changed by A6).

## A6. Automatic comment sync and resolution on GitHub

This amends A2 and A5.

```
POST   /reviews/{review_id}/forge/sync         import the pull request conversation into the latest revision -> {changes, new_commits, state}
```

- **Automatic sync:** while a pull request review is open and visible, the page calls the sync endpoint every 3 minutes and when the page regains focus (at most once a minute). It reads the pull request and its conversation with `gh` (two calls) and never fetches commits; `new_commits` tells the page that the pull request head differs from the reviewed head, and the page suggests **Check for new commits**.
- **Edits:** `published_comments.remote_body_hash` records the GitHub body last seen. When GitHub's body changes and the local comment was not edited since it was last sent or imported, the local comment takes GitHub's body and is marked edited. A GitHub comment that stands for several rtool comments (one review body) is never applied back. Rows written by a publish start without a hash, so the next sync only records it.
- **Deletions** on GitHub are not applied.
- **Resolution:** changing the status of a thread with a comment on GitHub resolves or unresolves the GitHub review thread (`resolveReviewThread` / `unresolveReviewThread` mutations through `gh api graphql`). If the mutation fails, the local status is not changed and the error is returned (502).
- **Network:** this replaces "GitHub is only contacted on an explicit user action" in A4 for the duration of an open pull request review.

## Plan changes

- A1 is part of M2 (model, states, API) and M3 (selection UI).
- A2 is a new milestone **M4b** after M4 (2-3 days): `ForgeAdapter`, `GitHubAdapter` via `gh`, linking, publish and its tests. Tests run against a fake `gh` executable placed first on `PATH`, which records its arguments and returns canned JSON; no real network call is made.
- Section 1 "out of scope": GitHub integration is replaced by "anything on GitHub beyond publishing comments".

## A7. One Sync action

"Check for new commits" and "GitHub comments" are merged into one **Sync** button (shortcut `r`).

```
POST   /reviews/{review_id}/sync               refresh with fetch, then publish unsent comments when linked -> {refresh, published, publish_error, unsent_comments}
```

- **Order:** the refresh runs first (A4 for pull request reviews, `git fetch` otherwise), then, if the review is linked and has unsent comments, they are published as in A2 with event `COMMENT`. `/sync` is the only way to publish: the separate publish endpoint and the draft option were removed.
- **Errors:** a failed fetch is a warning, as before. A failed publish (head mismatch, `gh` error) does not undo the refresh; its reason is returned in `publish_error`.
- **Label:** `GET /reviews/{review_id}` returns `unsent_comments`, and the button reads "Sync · N to send" on a linked review with unsent comments.
- **Linking:** when an unlinked review still has unsent comments after a sync, the page offers the matching open pull requests (or a number); choosing one links the review and syncs again.

## A8. Opening a pull request from its link

```
POST   /pulls/open                             {url} -> the pull request review (as POST /repos/{repo_id}/pulls/{number}/review)
```

- **Link:** `https://github.com/<owner>/<repository>/pull/<number>`, scheme optional, any suffix (`/files`, `#discussion_r...`) ignored. Anything else is rejected with 400.
- **Repository:** the registered repositories are checked first, then the repositories found by the home scan of A3; a repository matches when any of its remotes points to `<owner>/<repository>` (case-insensitive). The first match from the scan is registered. No match gives 404. The pull request is fetched from the matching remote, not necessarily `origin`.
- **UI:** an "Open pull request" field on the home page, and the client route `/github.com/<owner>/<repository>/pull/<number>`, which opens the review and replaces itself in the browser history.

## A9. GitHub-style rendering of comments and descriptions

Comments and pull request descriptions are rendered the way GitHub renders them, in the browser:

- GitHub Flavored Markdown with GitHub's line breaks (a single newline is a line break), alerts (`> [!NOTE]`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`), code highlighting, mermaid diagrams (drawn by the mermaid library with `securityLevel: strict`, loaded only when a diagram is shown) and `owner/repository#number` links.
- Raw HTML is parsed and then sanitized with GitHub's allow list (`rehype-sanitize` default schema); HTML comments are dropped.
- Images attached on GitHub need a signed-in user. They are loaded through:

```
GET    /forge/asset?url=                       an image attached on GitHub, downloaded with the gh token
```

- Only `https://github.com/user-attachments/assets/<uuid>` and `https://github.com/<owner>/<repository>/assets/<id>/<uuid>` are accepted (400 otherwise). The token comes from `gh auth token` at each download, is sent only to `github.com` (not on the redirect to the storage host) and is never stored. Only images up to 25 MB are returned (502 otherwise), with `Content-Security-Policy: sandbox` and `nosniff`; up to 64 images are kept in memory.
- This adds image downloads from GitHub to the outbound traffic of section 15.

## A10. Go units

`.go` files are parsed with tree-sitter (`tree-sitter-go`), in addition to the languages of the original spec. Go has no classes, so units map as follows:

- `func Name` is a `function` unit named `Name`; repeated names such as `init` get the usual `#2` suffix.
- `func (r *T) Name` is a `method` unit named `T.Name`: pointers, parentheses and type parameters of the receiver are dropped, so `*Stack[T]` gives `Stack`.
- Each type (struct, interface, alias or named type) is a `type` unit. In a grouped `type ( ... )` block each type is its own unit, and the `type (` and `)` lines stay in the module unit.
- Everything else (package clause, imports, variables, constants) is module-level code.

Methods are declared outside their type in Go, so the UI groups them: a method card is shown under the card of its type when the type is in the same file, or under a stand-in card ("only its methods changed here") otherwise. This only changes the layout; unit keys stay `(path, kind, qualified_name)`.

Each revision stores a signature of the unit rules it was built with (extractors with their versions, and the `file_level` globs). When a refresh finds the same commits but a different signature, for example after an upgrade that adds a language, it recomputes the units: a new revision is recorded only if they differ, otherwise the stored signature is updated.
