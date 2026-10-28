# rtool

Local, per-function code review for git branches. `rtool serve` opens a review UI on `localhost` that works directly on your repository, without needing a hosting service.

- Changes between a branch and its base (the same three-dot diff a pull request shows) are split into **reviewable units**: functions, methods, class bodies, TypeScript types, module-level code, and whole files for languages that are not parsed.
- An approval is tied to the **content** of a unit, not to a commit. After new commits, a rebase or a force-push, a unit with the same content stays approved.
- When an approved unit changes, you see the diff between the version you approved and the current one.
- Module-level code and whole files can also be approved **one selection of lines at a time**.
- "Since my last review" shows only what appeared or changed after you last clicked "Finish review".
- Comment threads are anchored to lines and follow them when the code moves. They can be sent to the GitHub pull request.

Python (`.py`, `.pyi`), TypeScript (`.ts`), TSX and JavaScript (`.js`, `.jsx`, `.mjs`, `.cjs`) are parsed with tree-sitter. Everything else is reviewed as whole files.

## Install

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), git, and Node.js 22.12+ to build the UI (`frontend/.nvmrc` pins 24).

```bash
npm --prefix frontend ci
npm --prefix frontend run build
uv tool install .
```

The UI build goes to `src/rtool/static/` and is packaged with the Python wheel, so rebuild it before reinstalling.

## Usage

```bash
rtool serve
```

Run inside a repository to register it and open the browser. To add other repositories, use **Browse...** on the home page: it lists the git repositories found in your home folder (up to four levels deep, skipping hidden folders, `node_modules`, `Library` and similar), and its **Browse folders** tab lets you pick any other folder. You can also paste a path. Options: `--repo PATH`, `--host 127.0.0.1`, `--port 8765`, `--no-open`.

The printed link contains a one-time session token. Opening it stores the token in a cookie for that browser; if you open rtool another way and see "Not authorized", use the printed link again.

```bash
rtool status feature/x --base develop
rtool refresh feature/x --fetch
```

`status` refreshes the review of a branch and prints the state of each changed unit. `refresh` records a new revision if any commit changed (`--fetch` runs `git fetch --prune` first). The base defaults to `base_branch` from `.rtool.toml`, then the first of `develop`, `main`, `master` that exists. An open review page picks up new revisions by itself.

### Reviewing

| State | Meaning |
|---|---|
| New | Not approved yet |
| Approved | You approved this exact content |
| Approved (moved) | You approved the same content under another name or path, which no longer exists |
| Changed since approval | You approved an earlier version; the diff shows approved to current by default |
| Partly approved | Some of the changed lines of a module or file are approved |
| Removed | The unit was deleted; approving it confirms the deletion |

A unit's own name does not count towards its content, so renaming a function with an unchanged body keeps the approval.

To approve part of a module or file, click changed lines in its diff (shift-click extends the selection) and press "Approve selection". An approved line needs review again if it or the line next to it changes.

Keyboard: `j` / `k` next and previous unit, `n` next unit to review, `a` approve or revoke (or approve the selected lines), `c` comment, `r` refresh.

### Comments

Click a line number to start a thread on that line. To comment on several lines, drag over their line numbers or shift-click another line number; the thread is sent to GitHub as a multi-line comment. Use "Comment on file" in a file header, or the conversation panel for comments on the whole review. Comments are Markdown. You can edit or delete your own comments, and delete a thread you started as long as nobody else replied to it (otherwise resolve it). Deleted threads disappear from rtool but stay on GitHub if they were already sent. When the code changes, a thread moves with its line. It follows a renamed unit, and becomes outdated, showing the original snippet, when its line is gone.

### Reviewing GitHub pull requests

For a repository with a GitHub remote, **Pull requests** on its card lists the open pull requests (read with the GitHub CLI, see below), each with its number of comments and how many review threads are still unresolved on GitHub. The list of reviews shows the same for rtool's own threads.

- **Review** downloads the pull request's code with `git fetch` into `refs/rtool/pull/<number>`, so your branches are not touched. It then starts a review against the pull request's base branch, already linked to the pull request.
- **Sync reviews** fetches the latest commits of every pull request you are reviewing in that repository and records new revisions. Pull requests that were closed or merged are marked as such.
- On a pull request review, **Refresh** with **fetch** does the same for that one pull request.

rtool only contacts GitHub when you press one of these buttons.

### Sending comments to GitHub

The "GitHub" button links the review to a pull request and sends the comments you have not sent yet as one pull request review. It uses the [GitHub CLI](https://cli.github.com), so run `gh auth login` once; rtool never stores a token.

- Lines inside the pull request diff become review comments on that line.
- Other lines, outdated threads and file threads become file comments that quote the line.
- Review threads go into the review body.
- Later replies and edits are sent as replies and edits of the published comments. Deleting or resolving a thread locally does not change GitHub.
- Sending is blocked while the pull request head differs from the reviewed commit, because line numbers would not match.
- "Keep as draft" leaves the review pending on GitHub. File comments are still posted immediately, because GitHub cannot keep them in a draft.

Approvals stay local.

## Configuration

Optional `.rtool.toml` at the repository root:

```toml
base_branch = "develop"
file_level = ["**/migrations/*.py", "*.lock", "package-lock.json", "pnpm-lock.yaml", "*.min.js"]
ignore = ["vendor/**", "docs/**"]
```

- `file_level`: globs reviewed as whole files instead of being parsed. Setting it replaces the defaults shown above.
- `ignore`: globs left out of the review entirely.
- Glob matching: a pattern without `/` matches the file name at any depth, `**/` matches any number of directories, and `*` stays within one directory.

## Data

Reviews, approvals and comments are stored in SQLite at `platformdirs.user_data_dir("rtool")/rtool.db` (on macOS `~/Library/Application Support/rtool`). Set `RTOOL_DATA_DIR` to use another directory.

A registered repository is remembered by its path and its first commit. If you move it, add it again from the new location and its reviews follow.

## Security

The server is meant for one person on one machine.

- **Network:** it listens on `127.0.0.1` by default and warns if you pass another `--host`.
- **Session token:** every API call needs the session token cookie (HttpOnly, SameSite=Strict).
- **Host check:** requests whose `Host` header is not `127.0.0.1:<port>` or `localhost:<port>` are rejected, which blocks DNS rebinding.
- **Git refs and files:** refs are validated with `git rev-parse --verify --end-of-options` before use. File contents are read only from the git object database.
- **Outbound traffic:** the only network access is `git fetch` when you ask for it and `gh` when you use the GitHub panel.

## Development

```bash
uv sync
npm --prefix frontend ci
uv run rtool serve --no-open
npm --prefix frontend run dev
```

The Vite dev server proxies `/api` to `127.0.0.1:8765`. To get the session cookie on the Vite origin, open `http://localhost:5173/api/health?token=<token>` once, using the token printed by `rtool serve` (set `RTOOL_TOKEN` to keep the same token across restarts).

Checks:

```bash
uv run ruff format --check . && uv run ruff check . && uv run basedpyright && uv run pytest
npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend test
npm --prefix frontend run build && npm --prefix frontend run e2e
```

The Playwright smoke test needs a browser once: `npx --prefix frontend playwright install chromium`. The GitHub tests use a fake `gh` from `tests/fakegh` and make no network calls.

Database migrations live in `src/rtool/storage/migrations` and run automatically at startup. After changing `src/rtool/storage/models.py`:

```bash
uv run alembic -c alembic.ini upgrade head
uv run alembic -c alembic.ini revision --autogenerate -m "describe the change"
rm dev.db
```

Spec changes made after the original specification are recorded in [docs/spec-amendments.md](docs/spec-amendments.md).
