# Design notes

How bussola works under the hood. The [README](../README.md) describes what it does from the user's side; this file covers the rules behind it.

## Units

A review compares a head ref with a base ref through their merge base, like a pull request. Every changed file is split into units:

| Kind | What it covers |
|---|---|
| `function` | A top-level function, with its decorators and leading comments |
| `method` | A function inside a class (or, in Go, a function with a receiver) |
| `class` | A class body without its methods |
| `type` | A TypeScript interface or type alias, or a Go type |
| `module` | Everything in a parsed file that is not inside another unit |
| `file` | A whole file of a language that is not parsed, or of a path in `file_level` |

Python, TypeScript, TSX, JavaScript and Go are parsed with tree-sitter. A file that does not parse falls back to a `file` unit.

A unit is identified by `(path, kind, qualified_name)`. Its content hash is computed on its text with trailing spaces removed, line endings normalized to LF and its own name replaced by a placeholder, so renaming a function with an unchanged body keeps its hash. Repeated names in one file get a positional suffix (`init`, `init#2`).

### Go

Go has no classes, so units map as follows:

- `func Name` is a `function` unit named `Name`.
- `func (r *T) Name` is a `method` unit named `T.Name`: pointers, parentheses and type parameters of the receiver are dropped, so `*Stack[T]` gives `Stack`.
- Each type (struct, interface, alias or named type) is a `type` unit. In a grouped `type ( ... )` block each type is its own unit, and the `type (` and `)` lines stay in the module unit.
- Everything else (package clause, imports, variables, constants) is module-level code.

Methods are declared outside their type, so the UI groups them: a method card is shown under the card of its type when the type is in the same file, or under a stand-in card ("only its methods changed here") otherwise. This only changes the layout.

## Revisions

A refresh resolves the head, base and merge base commits. When any of them changed, it records a new **revision** with a snapshot of every changed unit (base and head text, hashes and line mapping). Snapshots are never changed afterwards, so any earlier state of the review can be shown again.

Each revision also stores a signature of the unit rules it was built with: the extractors with their versions and the `file_level` globs. When a refresh finds the same commits but a different signature, for example after an upgrade that adds a language, it recomputes the units. A new revision is recorded only if they differ; otherwise the stored signature is updated.

## Approvals

An approval is tied to a unit key and to the head hash it was given for, not to a commit. A unit is `approved` when an active approval matches its current head hash. A unit whose content moved to another key, which no longer exists, keeps its approval as `approved (moved)`. A unit approved with an older hash is `changed`, and its diff defaults to approved-to-current.

### Approving selected lines

Functions, methods, classes and types are approved as a whole. `module` units and `file` units can also be approved one selection at a time.

For a unit with base text `B` and head text `H`, the line diff between `B` and `H` produces **changed rows**: lines added in head (`side = head`) and lines removed from base (`side = base`). Unchanged lines need no review. Each changed row has a content identity:

```
row_hash = sha256(side, normalized line, previous line, next line, occurrence)
```

- `normalized line` has trailing spaces removed and LF line endings; leading indentation is kept.
- `previous line` and `next line` are the neighbouring lines on the same side, so a row approved in one place does not count as approved somewhere else.
- `occurrence` separates rows that are identical in all of the above (0, 1, 2, ... in file order).

Anything that edits a row or its immediate neighbours produces a new identity, so the row needs review again.

The API receives a selection as line ranges on each side. The backend resolves the changed rows inside them and stores one `row_approvals` record per row, grouped by a `selection_id`. Revoking works per selection or per row. Nothing is deleted: revoked approvals keep a `revoked_at`.

A unit is `partial` when no whole-unit approval matches and some, but not all, of its changed rows are approved. It is `approved` when every changed row is. `partial` counts as still to review.

```
POST   /reviews/{review_id}/approvals          {unit_id, head_range?: [start, end], base_range?: [start, end]}
DELETE /reviews/{review_id}/row-approvals/{selection_id}
```

## Threads

A thread has a scope: `review` (the whole review), `file` or `unit`. As on GitHub, only `file` and `unit` threads can be resolved and count as open: a `review` thread is part of the conversation, like a pull request comment or a review summary, and resolving it is refused. A unit thread stores its unit key, side, first line offset inside the unit, the selected lines and three lines of context on each side.

At each refresh every unit thread, open or resolved, gets an anchor on the latest revision:

1. If its unit is unchanged, it keeps its offset.
2. If its unit changed, the selected line is searched in the new text; among several matches, the one whose surrounding lines match the stored context best wins, then the one closest to the old offset.
3. If its unit key is gone but a unit with the same hash exists (a rename or a move), it follows that unit.
4. Otherwise the line is searched in the other units of the same file, which covers a whole-file unit later split into functions.
5. If none of these finds the line, the thread is `outdated` and shows the original snippet.

## GitHub

bussola talks to GitHub only through the `gh` CLI, run with an argument list. Authentication is whatever `gh auth login` set up, and bussola never stores a token. If `gh` is missing or not authenticated, the UI says how to fix it and the rest keeps working.

### Pull request reviews

```
GET    /repos/{repo_id}/pulls                  open pull requests and the review already linked to each
POST   /repos/{repo_id}/pulls/{number}/review  fetch the pull request and start (or reuse) its review
POST   /repos/{repo_id}/pulls/sync             fetch every linked open pull request and refresh its review
POST   /pulls/open                             {url} -> the pull request review
```

- **Listing:** one GraphQL query returns the open pull requests with their comment count and the number of unresolved review threads, which `gh pr list` cannot report.
- **Fetching:** `git fetch --no-tags <remote> +refs/pull/<n>/head:refs/bussola/pull/<n> +refs/heads/<base>:refs/remotes/<remote>/<base>`. The review compares `refs/bussola/pull/<n>` with `<remote>/<base>`, so the user's branches are never modified. The base branch name from GitHub is checked with `git check-ref-format --branch` before use.
- **Linking:** table `forge_links` ties a review to its pull request and keeps its title, author, URL, state, description and last sync time.
- **Opening from a link:** `https://github.com/<owner>/<repository>/pull/<number>` (scheme optional, any suffix ignored). Registered repositories are checked first, then the repositories found by the home folder scan; a repository matches when any of its remotes points to `<owner>/<repository>`.

### Importing comments

One GraphQL query returns the pull request head, conversation comments, review summaries and review threads (path, line, start line, side, resolved state, comments).

- **Mapping:** a review thread becomes a unit thread on the same lines when the pull request head equals the reviewed head and the lines fall inside a changed unit; otherwise it becomes a file thread. A file thread with a line is placed on its line at a later import, once the reviewed head catches up. Conversation comments and non-empty review summaries become review threads.
- **Identity:** every imported comment is recorded in `published_comments` with its GitHub id, so nothing is imported twice and nothing imported is sent back.
- **Authors:** the GitHub user running `gh` maps to the current reviewer; others become reviewers named after their login.
- **Edits:** `published_comments.remote_body_hash` records the GitHub body last seen. When it changes and the local comment was not edited since it was last sent or imported, the local comment takes GitHub's body. Deletions on GitHub are not applied.
- **Resolution:** the resolved state follows GitHub at every import. Resolving or reopening a thread that is on GitHub runs the matching GraphQL mutation; if it fails, the local status is not changed.
- **Automatic sync:** while a pull request review is open and visible, the page calls `POST /reviews/{review_id}/forge/sync` every 3 minutes and when the page regains focus (at most once a minute). It never fetches commits; it reports when the pull request head differs from the reviewed head.

### Sending comments

```
POST   /reviews/{review_id}/sync               refresh with fetch, then publish unsent comments and mark approved files as viewed when linked
```

**Sync** refreshes first, then sends the comments that were not published yet (or were edited after publishing) as one pull request review with event `COMMENT`, at the pull request head commit:

| bussola thread | On GitHub |
|---|---|
| Unit thread, line in the pull request diff | Review comment on that line (`RIGHT` for head, `LEFT` for base) |
| Unit thread, line outside the diff, or outdated | File comment quoting the line number and the anchored snippet |
| File thread | File comment |
| Review thread | Part of the review body |
| Reply in a thread already on GitHub | Reply to that review comment |

Sending is blocked while the pull request head differs from the reviewed head, because line numbers would not match. A failed publish does not undo the refresh. Approvals are never sent as GitHub reviews.

### Viewed files

After sending comments, **Sync** marks as viewed on GitHub every file whose units are all `approved` or `approved (moved)` for the current reviewer in the latest revision, so a file changed after approval does not count. Through the forge adapter:

- `file_views` reads the pull request node id, its head and each file's `viewerViewedState` (GraphQL, paged by `gh api --paginate`).
- `set_files_viewed` marks the fully approved files that are not viewed yet with one GraphQL request of aliased `markFileAsViewed` mutations per 50 files. GitHub reports a refused file as an error on its alias, so only that file is reported as not marked. A request that fails as a whole (no permission, timeout) stops the marking and is reported once, without retrying file by file.

Nothing is marked while the pull request head differs from the reviewed head. `markFileAsViewed` takes no commit, so after marking, the head is read again; if it moved meanwhile, the files just marked are unmarked (they were not viewed before) and the sync asks to run again. A push after that point is handled by GitHub, which resets the viewed state of changed files. Files already viewed are left as they are, and files the user viewed by hand are never unmarked. Approved files that are not part of the pull request are skipped. When publishing comments already failed because the head moved, the viewed step is skipped. A failure never fails the sync, and GitHub is not contacted when no file is fully approved.

### Rendering

Comments and descriptions are rendered like on GitHub, in the browser: GitHub Flavored Markdown with GitHub's line breaks, alerts, code highlighting, mermaid diagrams (`securityLevel: strict`, loaded only when needed) and `owner/repository#number` links. Raw HTML is sanitized with GitHub's allow list (`rehype-sanitize` default schema).

Images attached on GitHub need a signed-in user, so they are loaded through `GET /forge/asset?url=`. Only `https://github.com/user-attachments/assets/<uuid>` and `https://github.com/<owner>/<repository>/assets/<id>/<uuid>` are accepted. The token comes from `gh auth token` at each download, is sent only to `github.com` (not on the redirect to the storage host) and is never stored. Only images up to 25 MB are returned, with `Content-Security-Policy: sandbox` and `nosniff`.

## Folder browser

Browsers do not reveal the absolute path of a folder picked with their native dialog, so bussola serves its own:

```
GET    /directories?path=                      folders inside path (default: the home directory), marking git repositories
GET    /directories/repositories               git repositories found under the home directory
```

The repository scan walks the home directory breadth first, up to four levels deep. It skips hidden folders, dependency and build folders (`node_modules`, `vendor`, `dist`, `build`, `target` and similar) and macOS media and `Library` folders, and it does not follow symlinks. It stops after five seconds or 500 results and reports that the list is incomplete. Both endpoints return only folder names, paths and whether a folder contains `.git`, never file names or contents.

## AI providers

Every AI feature goes through one interface, `AiProvider.complete(request, cancellation)`, which sends a system prompt, a user prompt and a JSON schema and returns the model's text. There are three implementations:

| Provider | Call | Structured output |
|---|---|---|
| `claude-code` | `claude -p --output-format json --no-session-persistence --safe-mode --strict-mcp-config --tools "" --system-prompt ... --json-schema ...`, prompt on stdin, in an empty temporary folder and its own process group | `structured_output` of the result, or its `result` text |
| `anthropic` | `POST {endpoint}/v1/messages` with `x-api-key` | `output_config.format` with the JSON schema |
| `openai-compatible` | `POST {endpoint}/chat/completions` with an optional `Authorization: Bearer` key and `max_completion_tokens` | `response_format` of type `json_schema`, strict |

`AiRunner.run(task, prompt, cancellation, content_hash)` builds the request from an `AiTask` (name, prompt version, system prompt and a Pydantic output model). The schema is made portable across providers: objects without a value schema get `additionalProperties: false`, every property is listed in `required`, and keywords that structured outputs reject (`minimum`, `maxLength`, `minItems`, `default` and similar) are left out. They still apply when the answer is validated. The answer, with an optional code fence (any language tag) removed, is validated against the model; an answer that is not JSON or does not match raises `AiOutputError` naming the first fields that failed. Each call runs in a worker thread. On timeout (`timeout` seconds from the configuration) or cancellation the HTTP connection is closed, or the `claude` process group is killed. When `claude` exits, bussola waits for it with `os.waitid(..., WNOWAIT)` so its process ID stays reserved, kills its process group, and only then reaps it; output is collected in chunks, so a leftover process holding the pipes cannot hold up the answer. Where `os.waitid` is missing (Python before 3.13 on macOS), only leftover processes that still hold the pipes are killed. Transport failures (dropped connections, unreadable answers) become `AiProviderError`, HTTP 429 and 5xx answers are retried, three attempts in all, after the `Retry-After` delay when the server gives one, and only while the pause fits in the overall timeout; the pause is cancellable. HTTP redirects are refused so a key never follows one, answers larger than 10 MB are refused, and loopback endpoints bypass any HTTP proxy. A batch records any error per item. `run_batch` runs a task over many items in order, reports progress after each item, records AI errors per item without stopping, stops on any other exception (a bug, not a model problem) while keeping earlier results, and on cancel stops and keeps the results already produced. A configuration error, a changed target, an unreachable endpoint (connection refused, unknown host, no route), a rejected key or rate limit (HTTP 401, 403 or 429) or the same error for two items in a row stop the batch, which reports why in `stopped_by`. A connection that breaks in the middle of one answer only fails that item.

Results are cached in `ai_results`, keyed by task, prompt version, provider, model, endpoint and the content hash given by the caller (the hash of what was sent). Changing the prompt, the model, the endpoint or the code therefore asks again; nothing else expires. Writes are upserts, so two requests caching the same result do not conflict. When the provider's model is not known (Claude Code without `model`), nothing is cached.

### Configuration

The user configuration (`config.toml`, `[ai]`) sets `provider`, `model`, `endpoint`, `timeout` and `api_key_env`. `.bussola.toml` may set `provider`, `model` and `endpoint`; anything else in its `[ai]` section is rejected. The repository applies only when the user chose a provider, so a cloned repository cannot turn AI on. The two are merged field by field when the repository keeps the user's provider. It may pick another provider only if that is `openai-compatible` or `none`, and it may not change the `model` or `endpoint` of `claude-code` or `anthropic`: those use the user's own account, so either attempt is reported as a configuration problem. When it picks another provider, only the repository's fields, the provider defaults and the user's `timeout` apply. Settings name the repository as their source only when it changes the result. `provider = "none"` turns AI off.

`.bussola.toml` keeps its `[ai]` section as raw data and it is validated only when AI settings are loaded, so a mistake there turns AI off for the repository, with the reason on its AI buttons, and reviews keep working.

Keys are read from the environment at each call: the variable named by `api_key_env`, or `ANTHROPIC_API_KEY` for `anthropic`. `openai-compatible` sends a key only when `api_key_env` names one. A key is used only with the user's own provider, endpoint and model (or that provider's defaults), so a cloned repository can neither redirect a key nor spend it on another provider or model. `claude-code` has no endpoint; one set in either file is ignored. When a repository's model or endpoint means the user's key would not be sent, the settings record that (`key_withheld`) and the provider reports it as a problem instead of sending no key. The installed `claude` is checked once per binary for `--safe-mode` (a failed check is retried after a minute).

```
GET    /ai                                     provider of the user configuration: label, model, endpoint, key variable and whether it is set, problem
GET    /repos/{repo_id}/ai                     the same with the repository's .bussola.toml applied
POST   /ai/test                                send a fixed prompt with a one-field schema to the user's provider
```

The UI shows AI buttons only when the repository's provider is configured, disabled with the reason when it cannot be used. On click the button reads the status again, and before an action first sends code to a target (the JSON list of provider, model and endpoint) it names the provider, model and endpoint and waits for confirmation, kept in the browser's local storage per target. The confirmed target is passed to the action, and an action's endpoint must check it with `require_target` against the settings it loads, so code is never sent to a target the user has not confirmed. These pieces (`AiActionButton`, `run_batch`, `SqlAiCache`, `require_target`) are used by the AI actions as they are added.
