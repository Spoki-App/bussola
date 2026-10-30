<p align="center"><img src="https://raw.githubusercontent.com/Spoki-App/bussola/main/frontend/public/favicon.svg" alt="" width="72" height="72"></p>

<h1 align="center">bussola</h1>

<p align="center">
  <a href="https://github.com/Spoki-App/bussola/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Spoki-App/bussola/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://pypi.org/project/bussola/"><img alt="PyPI" src="https://img.shields.io/pypi/v/bussola"></a>
  <img alt="Python 3.12 and 3.13" src="https://img.shields.io/badge/python-3.12%20%7C%203.13-3776ab">
  <a href="https://github.com/Spoki-App/bussola/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue"></a>
</p>

Local, per-function code review for git branches. `bussola serve` opens a review UI on `localhost` that works directly on your repository, without needing a hosting service.

*Bussola* is Italian for compass: it helps you find your way through a large change, one function at a time.

- Changes between a branch and its base (the same three-dot diff a pull request shows) are split into **reviewable units**: functions, methods, class bodies, TypeScript and Go types, module-level code, and whole files for languages that are not parsed.
- An approval is tied to the **content** of a unit, not to a commit. After new commits, a rebase or a force-push, a unit with the same content stays approved.
- When an approved unit changes, you see the diff between the version you approved and the current one.
- Module-level code and whole files can also be approved **one selection of lines at a time**.
- "Since my last review" shows only what appeared or changed after you last clicked "Mark as reviewed".
- Comment threads are anchored to lines and follow them when the code moves. They can be sent to the GitHub pull request.

Python (`.py`, `.pyi`), TypeScript (`.ts`), TSX, JavaScript (`.js`, `.jsx`, `.mjs`, `.cjs`) and Go (`.go`) are parsed with tree-sitter. Everything else is reviewed as whole files.

In Go, each function, method and type is its own unit. A method is named after its receiver type (`Service.Run`, also for `*Service` and `Stack[T]`), and its card is shown under the card of that type when both are in the same file. Each type in a grouped `type ( ... )` block is a separate unit.

## Install

Requirements: Python 3.12+, git, and the [GitHub CLI](https://cli.github.com) (`gh`) for the GitHub features only.

```bash
uv tool install bussola
```

`pipx install bussola` works too. bussola is developed on macOS and tested on macOS and Linux. Windows is not tested yet.

To install from a clone instead, you also need Node.js 22.12+ to build the UI (`frontend/.nvmrc` pins 24):

```bash
npm --prefix frontend ci
npm --prefix frontend run build
uv tool install .
```

The UI build goes to `src/bussola/static/` and is packaged with the Python wheel, so rebuild it before reinstalling.

## Usage

```bash
bussola serve
```

Run inside a repository to register it and open the browser. **Settings** (top right) opens a window with **Open pull request**, **Add repository**, **Code font**, **Diff layout** and **Line wrap**. To add other repositories, use **Browse...** under **Add repository**: it lists the git repositories found in your home folder (up to four levels deep, skipping hidden folders, `node_modules`, `Library` and similar), and its **Browse folders** tab lets you pick any other folder. You can also paste a path. Options: `--repo PATH`, `--host 127.0.0.1`, `--port 8765`, `--no-open`.

The printed link contains a one-time session token. Opening it stores the token in a cookie for that browser; if you open bussola another way and see "Not authorized", use the printed link again.

```bash
bussola status feature/x --base develop
bussola refresh feature/x --fetch
```

`status` refreshes the review of a branch and prints the state of each changed unit. `refresh` records a new revision if any commit changed (`--fetch` runs `git fetch --prune` first). The base defaults to `base_branch` from `.bussola.toml`, then the first of `develop`, `main`, `master` that exists. An open review page picks up new revisions by itself.

### Reviewing

The review header has two actions:

- **Sync** (shortcut `r`) first fetches the branch from its remote (on a pull request review: the pull request's latest commits and comments from GitHub), then records any new commits as a new revision. Approvals of units that did not change are kept. If the remote or GitHub cannot be reached, it checks the local branch and says so. When the review is linked to a pull request, it then sends your unsent comments to GitHub (see below); the button shows how many are waiting, as in "Sync · 3 to send".
- **Mark as reviewed** remembers where you are. It approves and closes nothing; the **Since my last review** filter then shows only what changes after this point.

Image files changed in the review (PNG, JPEG, GIF, WebP, AVIF, BMP, ICO, SVG) show the image before and after the change, with its size; SVG files also keep their text diff.

Diffs are syntax highlighted with the colors GitHub uses, by file extension (Python, TypeScript, JavaScript, Go, Java, Kotlin, Ruby, Rust, PHP, C/C++, C#, Swift, SQL, shell, YAML, JSON, HTML/XML, CSS, Markdown and others). The whole unit is highlighted at once, so strings and comments that span several lines keep their color even when part of them is collapsed.

**Code font** in **Settings** sets the font and size used for code. It suggests the common coding fonts installed on your computer; in Chrome and Edge, **List all installed monospaced fonts** asks the browser for permission and lists every installed monospaced font. You can also type the name of any installed font. **Ligatures** turns ligatures on or off for fonts that have them (Fira Code, JetBrains Mono, Victor Mono and similar; SF Mono, Menlo and Monaco have none), and **Font features** turns on OpenType features such as stylistic sets (`ss01`, Monaspace's ligatures) or `zero`. The choice is kept in this browser.

**Diff layout** in **Settings** chooses how diffs are shown: **Split** puts the old code on the left and the new code on the right, **Unified** shows one column, and **Automatic** (the default) splits a unit only when it rewrites lines (a block of changes with both removed and added lines) and the window is at least as wide as the threshold (1400px unless you change it). New and deleted units stay in one column, and the choice is made again when the window is resized. The same switch sits in the review bar next to the unit filter. The choice is kept in this browser.

Long lines in the diff wrap by default. A wrapped line keeps the indentation of its first part and shows its line number only once, and clicking any part of it selects the whole line. Turn wrapping off with **Wrap long lines** under **Line wrap** in **Settings**, or with **Wrap lines** above the diff; lines then stay on one row and the diff scrolls sideways. Units shown in split view always wrap, so the old and new code stay side by side. The choice is kept in this browser.

Units that still need review start open and the others closed. Approving a unit closes its card, and a card opens again when its unit needs review again (approval revoked, or new changes).

| State | Meaning |
|---|---|
| New | Not approved yet |
| Approved | You approved this exact content |
| Approved (moved) | You approved the same content under another name or path, which no longer exists |
| Changed since approval | You approved an earlier version; the diff shows approved to current by default |
| Partly approved | Some of the changed lines of a module or file are approved |
| Removed | The unit was deleted; approving it confirms the deletion |

Methods are shown inside their class's card. When only methods of a class changed, the class still gets a card, marked "no changes outside its methods", with nothing to approve.

A unit's name starts with its module, muted: the dotted Python module (`bussola.review.anchoring.find_line`, without a leading `src/` or `__init__`), the file path without extension for TypeScript and JavaScript, and the package import path from `go.mod` for Go. Methods keep their class too (`shop.billing.invoices.InvoiceService.create`), with the module muted and the unit's own name in bold. A title too long for its card is cut at the start with an ellipsis, so the name stays visible; hover it to see it whole. The box next to the unit filters finds units by any part of their module, name or path.

A unit's own name does not count towards its content, so renaming a function with an unchanged body keeps the approval.

To approve part of a module or file, click changed lines in its diff (shift-click extends the selection) and press "Approve selection". An approved line needs review again if it or the line next to it changes.

Keyboard: `j` / `k` next and previous unit, `n` next unit to review, `a` approve or revoke (or approve the selected lines), `c` comment, `r` check for new commits.

### Comments

Click a line number to start a thread on that line. To comment on several lines, drag over their line numbers or shift-click another line number; the thread is sent to GitHub as a multi-line comment. Use "Comment on file" in a file header, or the conversation panel for comments on the whole review. Comments and pull request descriptions are rendered like on GitHub: GitHub Flavored Markdown (tables, task lists, line breaks), `> [!NOTE]` style alerts, safe HTML, highlighted code, mermaid diagrams, `owner/repo#123` links, and images attached on GitHub (downloaded through bussola with your `gh` login, since GitHub only serves them to signed-in users). You can edit or delete your own comments, and delete a thread you started as long as nobody else replied to it (otherwise resolve it). As on GitHub, only line and file threads can be resolved and count as open; comments on the whole review are part of the conversation. Deleted threads disappear from bussola but stay on GitHub if they were already sent. When the code changes, a thread moves with its line. It follows a renamed unit, and becomes outdated, showing the original snippet, when its line is gone.

### Reviewing GitHub pull requests

For a repository with a GitHub remote, **Pull requests** on its card lists the open pull requests (read with the GitHub CLI, see below), each with its number of comments and how many review threads are still unresolved on GitHub. The list of reviews shows the same for bussola's own threads.

- **Open pull request** in **Settings** takes a GitHub pull request link (`https://github.com/<owner>/<repository>/pull/<number>`, with or without `/files` or an anchor). bussola looks for a repository you added whose remote points to that GitHub repository; if there is none, it scans your home folder as **Browse** does, adds the first clone it finds and uses it. Then it opens the pull request review as **Review** below does. You can also open `http://127.0.0.1:<port>/github.com/<owner>/<repository>/pull/<number>` directly: replace `https://` in a GitHub link with the bussola address.
- **Review** downloads the pull request's code with `git fetch` into `refs/bussola/pull/<number>`, so your branches are not touched. It then starts a review against the pull request's base branch, already linked to the pull request.
- **Sync reviews** fetches the latest commits of every pull request you are reviewing in that repository and records new revisions. Pull requests that were closed or merged are marked as such. A review of a branch that you linked to a pull request is refreshed the same way its own **Sync** does it: the branch is fetched and the pull request comments are imported.
- The filter above the repositories (**Open**, **Merged**, **Closed**, **All**) shows open pull requests and branch reviews by default; reviews of merged or closed pull requests are hidden until you pick another filter. Each repository says how many reviews the filter hides, and the choice is kept in this browser.
- On a pull request review, **Sync** does the same for that one pull request.
- The pull request's description is shown under the review header (collapsible, long ones are cut short until you click **Show all**) and is updated at every sync.
- Comments already on GitHub are brought into the review each time: line comments become threads on the same lines (or on the file when the line is outdated or outside the changed units), conversation comments and review summaries become review comments (which, like on GitHub, cannot be resolved), and resolved threads stay resolved. Your own GitHub comments show as yours, and replying in bussola to an imported thread sends the reply to GitHub. Comments that came from GitHub link back to it.
- While a pull request review is open, bussola syncs its comments with GitHub every 3 minutes, and again when you come back to the page. New comments and replies are added, comments edited on GitHub are updated (unless you edited them in bussola and have not sent the edit yet), and threads resolved or reopened on GitHub follow. The header says when the last sync happened, and tells you when new commits were pushed so you can **Sync**. Comments deleted on GitHub stay in bussola.
- Resolving or reopening a thread that is also on GitHub does the same on GitHub. If GitHub refuses (for example, you lack write access), the thread stays as it was and the error is shown.

bussola contacts GitHub only when you press one of these buttons, or for the automatic sync while a pull request review is open.

### Opening bussola:// links

Register the `bussola://` URL scheme once, so links in GitHub, Slack or a terminal open straight in bussola:

```bash
bussola install-handler
```

| Link | Opens |
|---|---|
| `bussola://` | the home page |
| `bussola://review?repo=<owner>/<name>&pr=<number>` | the review of that pull request, started if there is none yet |
| `bussola://review?repo=<owner>/<name>&pr=<number>&path=src/app.py&line=42` | the same review, scrolled to the unit containing that line |
| `bussola://review?repo=<owner>/<name>&pr=<number>&thread=<id>` | the same review, scrolled to that thread |
| `bussola://github.com/<owner>/<name>/pull/<number>` | a GitHub pull request link with `https` replaced by `bussola`; `/files` and other pages of the pull request work too, and a `#discussion_r<id>` anchor scrolls to the imported thread |

If bussola is not running, the link starts `bussola serve --no-open` in the background on `127.0.0.1:8765`, waits for it, then opens the browser. A running `bussola serve` writes its address and session token to `server.json` in the data folder (readable only by you) so links can find it. The repository is found as **Open pull request** finds it; if there is no local clone, the home page opens with **Add a repository** filtered on its name, and the pull request opens once you add it. `bussola open-link '<link>'` does the same from a terminal.

- **macOS:** builds `~/Applications/bussola.app`, a small AppleScript app that declares the scheme, and registers it with Launch Services. Opening the app itself opens bussola.
- **Linux:** writes `bussola-url-handler.desktop` to `~/.local/share/applications` (or `$XDG_DATA_HOME/applications`) and makes it the default for `x-scheme-handler/bussola` with `xdg-mime`.
- **Windows:** writes the `HKCU\Software\Classes\bussola` registry keys for the current user.

The handler runs the Python that ran `install-handler`, so run it again after reinstalling bussola somewhere else. `bussola uninstall-handler` removes the registration.

### Sending comments to GitHub

**Sync** sends the comments you have not sent yet as one pull request review. A pull request review is already linked; for a branch review with unsent comments, Sync offers the open pull requests of that branch (or a PR number) and sends once you pick one. It uses the [GitHub CLI](https://cli.github.com), so run `gh auth login` once; bussola never stores a token.

- Lines inside the pull request diff become review comments on that line.
- Other lines, outdated threads and file threads become file comments that quote the line.
- Review threads go into the review body.
- Later replies and edits are sent as replies and edits of the published comments. Deleting a thread locally does not change GitHub; resolving or reopening one that is on GitHub does.
- Sending is blocked while the pull request head differs from the reviewed commit, because line numbers would not match.

Approvals stay local, but **Sync** ticks "Viewed" on GitHub for every file whose changes you have all approved. Files approved only in part, or changed since you approved them, are left alone, and files you marked by hand are never unmarked. If the pull request gets new commits while files are being marked, the marks are undone and Sync asks you to run it again. A file that cannot be marked is listed as an error after the sync; the rest of the sync still goes through.

## Configuration

Optional `.bussola.toml` at the repository root:

```toml
base_branch = "develop"
file_level = ["**/migrations/*.py", "*.lock", "package-lock.json", "pnpm-lock.yaml", "*.min.js"]
ignore = ["vendor/**", "docs/**"]
```

- `file_level`: globs reviewed as whole files instead of being parsed. Setting it replaces the defaults shown above.
- `ignore`: globs left out of the review entirely.
- Glob matching: a pattern without `/` matches the file name at any depth, `**/` matches any number of directories, and `*` stays within one directory.

## Data

Reviews, approvals and comments are stored in SQLite at `platformdirs.user_data_dir("bussola")/bussola.db` (on macOS `~/Library/Application Support/bussola`). Set `BUSSOLA_DATA_DIR` to use another directory.

A registered repository is remembered by its path and its first commit. If you move it, add it again from the new location and its reviews follow.

## Security

The server is meant for one person on one machine.

- **Network:** it listens on `127.0.0.1` by default and warns if you pass another `--host`.
- **Session token:** every API call needs the session token cookie (HttpOnly, SameSite=Strict).
- **Host check:** requests whose `Host` header is not `127.0.0.1:<port>` or `localhost:<port>` are rejected, which blocks DNS rebinding.
- **Git refs and files:** refs are validated with `git rev-parse --verify --end-of-options` before use. File contents are read only from the git object database.
- **bussola:// links:** a link only chooses what to open. Its parameters are validated (repository name, numbers, a relative file path, a thread id), anything else in it is ignored, and no link approves, resolves, sends or deletes anything.
- **Opening links:** GitHub links are opened by the server in your default browser, as a new tab, so they work even when the bussola page runs in an app-style window. The server only opens `https://github.com` addresses.
- **Outbound traffic:** the only network access is `git fetch` when you ask for it, `gh` when you sync or have a pull request review open, and downloads of images attached on GitHub shown in comments and descriptions.
- **Rendered Markdown:** HTML in comments and descriptions is sanitized with GitHub's rules before it is shown. Attached images are served from `/api/forge/asset` only for `https://github.com/.../assets/...` links and only when they are images, with a sandboxing Content-Security-Policy.

## Status

bussola is used on real pull requests, but it is young. Until 1.0, commands, options and the UI may change between minor versions. Your data is kept across upgrades: the database is migrated automatically at startup, and a change to how files are split into units is applied to existing reviews at their next **Sync**, without losing approvals of units that did not change.

## FAQ

<details><summary><b>Does my code leave my machine?</b></summary>

No. bussola reads your local clone. It only talks to your git remote when you sync, and to GitHub through your own `gh` login when you use the pull request features.
</details>

<details><summary><b>Do I need GitHub?</b></summary>

No. Any two branches of a local repository can be reviewed. GitHub adds pull request listing, comment import and sending comments back.
</details>

<details><summary><b>Is it a replacement for GitHub's review UI?</b></summary>

It is a place to do the reading. Approvals stay with you and follow the code across force-pushes and rebases; comments go back to the pull request so the discussion stays where your team has it.
</details>

<details><summary><b>Can several people review the same branch?</b></summary>

Each person runs bussola on their own machine and keeps their own approvals. Comments are shared through the pull request.
</details>

<details><summary><b>What about other languages?</b></summary>

Files that are not parsed are still reviewed, as whole files with line selections. Adding a language means adding a tree-sitter extractor in `src/bussola/units/extractors/`; see [CONTRIBUTING.md](https://github.com/Spoki-App/bussola/blob/main/CONTRIBUTING.md).
</details>

## Contributing

See [CONTRIBUTING.md](https://github.com/Spoki-App/bussola/blob/main/CONTRIBUTING.md) for the development setup and checks, and [docs/design.md](https://github.com/Spoki-App/bussola/blob/main/docs/design.md) for how units, revisions, approvals, threads and the GitHub integration work. Report security issues as described in [SECURITY.md](https://github.com/Spoki-App/bussola/blob/main/SECURITY.md).

## License

bussola is released under the [MIT License](https://github.com/Spoki-App/bussola/blob/main/LICENSE). It is not affiliated with GitHub; GitHub is a trademark of GitHub, Inc.

The UI bundles third-party libraries; their licenses are listed in `THIRD_PARTY_LICENSES.md`, which the UI build writes next to the app and the package ships. Diagrams use [elkjs](https://github.com/kieler/elkjs) (EPL-2.0), whose source code is available from that repository.
