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

Run inside a repository to register it and open the browser. **Settings** (top right) opens a window with the categories on the left: **Pull requests** (**Open pull request**), **Repositories** (**Add repository**), **Appearance** (**Code font**), **Diff** (**Diff layout**, **Line wrap**) and **AI** (**AI provider**, **AI prompts**). The search field at the top finds a setting by its name or description in every category and highlights the match; the arrow keys move between categories and Esc closes the window. To add other repositories, use **Browse...** under **Add repository**: it lists the git repositories found in your home folder (up to four levels deep, skipping hidden folders, `node_modules`, `Library` and similar), and its **Browse folders** tab lets you pick any other folder. You can also paste a path. Options: `--repo PATH`, `--host 127.0.0.1`, `--port 8765`, `--no-open`.

The printed link contains a one-time session token. Opening it stores the token in a cookie for that browser; if you open bussola another way and see "Not authorized", use the printed link again.

```bash
bussola status feature/x --base develop
bussola refresh feature/x --fetch
```

`status` refreshes the review of a branch and prints the state of each changed unit. `refresh` records a new revision if any commit changed (`--fetch` runs `git fetch --prune` first). The base defaults to `base_branch` from `.bussola.toml`, then the first of `develop`, `main`, `master` that exists. An open review page picks up new revisions by itself.

### Shell completion

Tab completes commands, options, paths for `--repo` and, for the branch argument and `--base`, the local and remote branches of the repository in the current folder (or of `--repo`). Completion only reads refs with `git for-each-ref`: it never fetches, touches the network or starts the server, and outside a repository it offers no branches.

Run `bussola --install-completion` once in your shell to set it up (in PowerShell it also sets the execution policy of your user to `Unrestricted`, so you may prefer the line below), or add the line for your shell yourself (`bussola --show-completion` prints the script for the current shell):

| Shell | Add to | Line |
|---|---|---|
| bash | `~/.bashrc` | `eval "$(_BUSSOLA_COMPLETE=source_bash bussola)"` |
| zsh | `~/.zshrc`, after `compinit` | `eval "$(_BUSSOLA_COMPLETE=source_zsh bussola)"` |
| fish | `~/.config/fish/config.fish` | `_BUSSOLA_COMPLETE=source_fish bussola \| source` |
| PowerShell | `$PROFILE` | `$env:_BUSSOLA_COMPLETE = "source_powershell"; bussola \| Out-String \| Invoke-Expression; Remove-Item Env:_BUSSOLA_COMPLETE` |

Open a new shell afterwards.

### Reviewing

The review header has two actions:

- **Sync** (shortcut `r`) first fetches the branch from its remote (on a pull request review: the pull request's latest commits and comments from GitHub), then records any new commits as a new revision. Approvals of units that did not change are kept. If the remote or GitHub cannot be reached, it checks the local branch and says so. When the review is linked to a pull request, it then sends your unsent comments to GitHub (see below); the button shows how many are waiting, as in "Sync · 3 to send".
- **Mark as reviewed** remembers where you are. It approves and closes nothing; the **Since my last review** filter then shows only what changes after this point.

The unit filter (**All**, **To review**, **Since my last review**) is kept in this browser, like the diff layout, so a reload or another review opens with the same choice.

Image files changed in the review (PNG, JPEG, GIF, WebP, AVIF, BMP, ICO, SVG) show the image before and after the change, with its size; SVG files also keep their text diff.

Diffs are syntax highlighted with the colors GitHub uses, by file extension (Python, TypeScript, JavaScript, Go, Java, Kotlin, Ruby, Rust, PHP, C/C++, C#, Swift, SQL, shell, YAML, JSON, HTML/XML, CSS, Markdown and others). The whole unit is highlighted at once, so strings and comments that span several lines keep their color even when part of them is collapsed. In a block of changed lines, each removed line is paired with the most similar added line of the block, and the words that changed between the two get a stronger background; when a name is renamed, only the part of it that changed is marked, such as `_` in `_refresh_balance` and `_credit` in `refresh_credit_balance`. Lines of the block with no counterpart, such as a new comment, are marked whole.

**Code font** in **Settings** sets the font and size used for code. It suggests the common coding fonts installed on your computer; in Chrome and Edge, **List all installed monospaced fonts** asks the browser for permission and lists every installed monospaced font. You can also type the name of any installed font. **Ligatures** turns ligatures on or off for fonts that have them (Fira Code, JetBrains Mono, Victor Mono and similar; SF Mono, Menlo and Monaco have none), and **Font features** turns on OpenType features such as stylistic sets (`ss01`, Monaspace's ligatures) or `zero`. The choice is kept in this browser.

**Diff layout** in **Settings** chooses how diffs are shown: **Split** puts the old code on the left and the new code on the right, **Unified** shows one column, and **Automatic** (the default) splits a unit only when it rewrites lines (a block of changes with both removed and added lines) and the window is at least as wide as the threshold (1400px unless you change it). New and deleted units stay in one column, and the choice is made again when the window is resized. The same switch sits at the top of the **Files** bar, under the unit filter and the search box, so all three stay at hand while you scroll; with the **Files** bar hidden they move above the units. The choice is kept in this browser.

Lines are matched ignoring spaces, so a line that only changed its indentation, such as code moved into a new `try` or loop, stays next to its old version in split view, and only the indentation it gained or lost is highlighted, at the start of the line so the marks line up. In a block that modifies lines, the lines added or removed with no counterpart, such as the new `try:` itself, are highlighted in full.

Long lines in the diff wrap by default. A wrapped line keeps the indentation of its first part and shows its line number only once, and clicking any part of it selects the whole line. Turn wrapping off with **Wrap long lines** under **Line wrap** in **Settings**, or with the wrap button that appears at the bottom right of an open unit when the mouse is over it; lines then stay on one row and the diff scrolls sideways. In split view each side scrolls sideways on its own, with a scroll bar under each side that stays at the bottom of the window, so the old and new lines stay side by side; a sideways swipe or Shift with the mouse wheel scrolls the side under the pointer. The choice is kept in this browser.

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

To approve part of a module or file, click a changed line in its diff (click it again to clear the selection), shift-click another to select the lines between them, or drag over the line numbers to select the lines covered (the page scrolls at the top and bottom edges), and press "Approve selection". An approved line needs review again if it or the line next to it changes.

Keyboard: `j` / `k` next and previous unit, `n` next unit to review, `a` approve or revoke (or approve the selected lines), `c` comment, `r` check for new commits, `t` show or hide the conversation panel. Cmd/Ctrl+click a name to go to its definition or usages.

### Comparing code

Code moved or extracted elsewhere is found automatically: a block of removed lines and a block of added lines with nearly the same code, in the same file or in another one, are linked both ways. The unit the code left gets **moved to `validate`**, the unit it arrived in gets **moved from `checkout`**, and a click on either opens the two blocks side by side, with the changed words highlighted. Moves that kept the code as it was, apart from indentation and blank lines, are marked **identical**. Small blocks (fewer than three lines with some code on them) and trivial lines such as `}` or `else:` are left out, so short or common snippets do not show up as moves.

To compare any two pieces of code, select lines by their numbers in a unit, as for a comment, and choose **Compare with...**. Then select a second range, in any unit or file of the review, and choose **Compare with first range**. **Cancel** in the bar at the bottom drops the first range.

### Comments

Click a line number to start a thread on that line. To comment on several lines, drag over their line numbers or shift-click another line number; the thread is sent to GitHub as a multi-line comment. Use "Comment on file" in a file header, or the conversation panel for comments on the whole review. Comments and pull request descriptions are rendered like on GitHub: GitHub Flavored Markdown (tables, task lists, line breaks), `> [!NOTE]` style alerts, safe HTML, highlighted code, mermaid diagrams, `owner/repo#123` links, and images attached on GitHub (downloaded through bussola with your `gh` login, since GitHub only serves them to signed-in users). Every comment box has **Write** and **Preview** tabs (Cmd/Ctrl+Shift+P switches between them) and a toolbar for headings, bold, italic, strikethrough, code, code blocks, quotes, links and lists; Cmd/Ctrl+B, I, K and E add bold, italic, a link and inline code. You can edit or delete your own comments, and delete a thread you started as long as nobody else replied to it (otherwise resolve it). As on GitHub, only line and file threads can be resolved and count as open; comments on the whole review are part of the conversation. Deleted threads disappear from bussola but stay on GitHub if they were already sent. When the code changes, a thread moves with its line. It follows a renamed unit, and becomes outdated, showing the original snippet, when its line is gone.

### Code navigation

Cmd+click (Ctrl+click on Linux and Windows) a name in a diff to navigate, as in IntelliJ, in Python, TypeScript/TSX, JavaScript and Go files:

- On a call or any other use of a name, bussola looks for its definition. On the name of a function, method, class or module level variable where it is defined, it lists its usages.
- When there is exactly one result, it opens directly: if it is part of the review the page scrolls to that unit and highlights the line, otherwise the file opens in a window as described below.
- Otherwise a list opens next to the pointer: definitions first, then usages grouped by file, each with its line, the function, method or class it is in (or **module level**) and a preview, and results inside the review marked **in review**. Use the arrow keys, Enter and Esc.
- A result outside the review opens the file at the reviewed commit in a window, highlighted and scrolled to the line, with a link to the file on GitHub when the branch has a GitHub remote. Cmd/Ctrl+click works there too, and **Back** returns along the chain.
- On a name imported from a framework or library outside the repository (Django, React, the Go standard library and so on), the same popup shows its documentation instead. First the full name, the signature and the docstring or doc comment, as Markdown: from the language server when one is installed, otherwise read from the installed source of the library without running it. Then the package and its version when known, a **Documentation** link to the page of that function, class or method when one can be built (docs.python.org, nodejs.org, pkg.go.dev, react.dev, the Django, FastAPI, Flask, Requests, NumPy, pandas, lodash and Express references, or a search of the package's Read the Docs site), and a separate **Package home** link to the package documentation, homepage, PyPI or npm. When the package is installed in the repository (`.venv` or `venv`, `node_modules`) or in the Go module cache or `GOROOT`, **Open source** shows the file of the definition in the window, read only. A name without a docstring still shows its signature, and when nothing is found the popup says so. Doc text is rendered without scripts and without loading images.
- While Cmd (Ctrl) is held, the name under the pointer is underlined, with a pointer cursor, when it has somewhere to go. Keywords, strings, comments, punctuation and names with no result are never underlined.

A plain click on a name highlights every occurrence of it in the same unit, on both sides of the diff, to see where it is read or written. Other units and files are left alone. Click another name to move the highlight, and click elsewhere or press Esc to clear it.

Results come from an index of the repository at the reviewed commit, built with tree-sitter in the background when the review opens and kept per commit. It matches names, so it needs nothing installed but can list unrelated functions with the same name. When a language server is on your `PATH`, its precise answers are used instead: `basedpyright-langserver` or `pyright-langserver` for Python, `typescript-language-server` for TypeScript and JavaScript, `gopls` for Go. It runs on a copy of the reviewed commit, never on your working tree. If the server finds nothing, fails or takes more than five seconds, the index answers instead. The first time you navigate in a language without a server, a note shows the command that installs one; it is shown once.

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
- **Merge** on an open pull request review merges it on GitHub, as GitHub's merge button does: **Create a merge commit**, **Squash and merge** or **Rebase and merge**, only those the repository allows, starting from the method GitHub selects for you. For a merge commit or a squash, the commit title and message are prefilled like on GitHub and can be edited. **Delete the branch after merging** deletes the head branch, unless the repository already deletes merged branches. When merging is blocked (a draft, conflicts, a branch out of date, a review required or requested changes, failing or pending checks, or commits pushed since the reviewed revision, which **Sync** brings into the review first) the reasons are listed and the button stays off, and if GitHub refuses the merge its reason is shown. After a merge the pull request state and comments are refreshed.

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
| `bussola://review?repo=<owner>/<name>&pr=<number>&path=src/app.py&line=42` | the same review, scrolled to that line, which stays highlighted |
| `bussola://review?repo=<owner>/<name>&pr=<number>&thread=<id>` | the same review, scrolled to that thread (`comment=<GitHub comment id>` works too) |
| `bussola://github.com/<owner>/<name>/pull/<number>` | a GitHub pull request link with `https` replaced by `bussola`; `/files` and other pages of the pull request work too, and a comment anchor (`#discussion_r<id>` or `#r<id>`) scrolls to the imported thread |

In a pull request review, bussola copies these links for you: **Copy bussola link** next to **View on GitHub** for the review, the link icon after a unit's name for its first line, the link icon in a thread's header for the thread, and the link icon that appears next to the new line number when you hover a line for that line (removed lines have none).

If bussola is not running, the link starts `bussola serve --no-open` in the background on `127.0.0.1:8765`, waits for it, then opens the browser. Each running `bussola serve` writes its address and session token to a file in `servers/` in the data folder (readable only by you) once it is listening, so links can find it; a link prefers the server on port 8765. A server started by a link does not add your home folder as a repository. The repository is found as **Open pull request** finds it; if there is no local clone, the home page asks you to clone it and add its folder (**Browse...** starts filtered on its name), and the pull request opens once you add it (or the prompt says the folder is not a clone of it). If GitHub cannot be reached, a link to a pull request you are already reviewing opens that review as it is. `bussola open-link '<link>'` does the same from a terminal. A link that cannot be opened (not a valid link, or the server did not start) is recorded in `open-link.log` in the data folder, since the operating system shows no output.

- **macOS:** builds `~/Applications/bussola.app`, a small AppleScript app that declares the scheme, and registers it with Launch Services. It keeps the `PATH` of the shell that ran `install-handler`, so a server it starts finds `gh` and `git`. Opening the app itself opens bussola.
- **Linux:** writes `bussola-url-handler.desktop` to `~/.local/share/applications` (or `$XDG_DATA_HOME/applications`) and makes it the default for `x-scheme-handler/bussola` with `xdg-mime`. Like on macOS, it keeps the `PATH` of the shell that ran `install-handler`.
- **Windows:** writes the `HKCU\Software\Classes\bussola` registry keys for the current user.

The handler runs the Python that ran `install-handler`, and keeps the `BUSSOLA_DATA_DIR` it was run with, so run it again after reinstalling bussola somewhere else or moving your data. `bussola uninstall-handler` removes the registration, and on Linux also the `x-scheme-handler/bussola` default that `xdg-mime` wrote to `mimeapps.list`.

### Sending comments to GitHub

**Sync** sends the comments you have not sent yet as one pull request review. A pull request review is already linked; for a branch review with unsent comments, Sync offers the open pull requests of that branch (or a PR number) and sends once you pick one. It uses the [GitHub CLI](https://cli.github.com), so run `gh auth login` once; bussola never stores a token.

- Lines inside the pull request diff become review comments on that line.
- Other lines, outdated threads and file threads become file comments that quote the line.
- Review threads go into the review body.
- Comments added by the [AI review](#ai-review) end with a line saying they were generated by the bussola AI review, with the provider and model.
- Later replies and edits are sent as replies and edits of the published comments. Deleting a thread locally does not change GitHub; resolving or reopening one that is on GitHub does.
- Sending is blocked while the pull request head differs from the reviewed commit, because line numbers would not match.

Approvals stay local, but **Sync** ticks "Viewed" on GitHub for every file whose changes you have all approved. Files approved only in part, or changed since you approved them, are left alone, and files you marked by hand are never unmarked. If the pull request gets new commits while files are being marked, the marks are undone and Sync asks you to run it again. A file that cannot be marked is listed as an error after the sync; the rest of the sync still goes through.

### Themes

**Theme** under **Appearance** in **Settings** chooses the colors: **System** (the default) follows the light or dark setting of your computer, **Light** and **Dark** are bussola's own palettes, and you can import any VS Code color theme. Pick the `.json` file inside the theme extension (usually in its `themes` folder; comments and trailing commas are fine). Importing a `.vsix` package is not supported yet. The theme `type` (`light` or `dark`) chooses the palette that fills in the colors the theme does not set; without a `type` the background decides. Themes that take their colors from another file with `include` are not followed: bussola says so and uses its own palette for those colors, so import the file they include instead.

Themes installed in VS Code, VS Code Insiders, Cursor, Windsurf or VSCodium show up in the same list, grouped by editor, with no import step: bussola reads the extensions folder of each editor (`~/.vscode/extensions`, `~/.cursor/extensions` and so on, the same folders on Windows under your user folder) and the themes that come with the editor itself, such as Dark+ and Light+, when the editor is installed in its usual place. Only the latest version of each extension is listed. Choosing one reads its colors at that moment, following `include` within the extension, and keeps a copy in the browser, so it keeps working if the editor is closed; choosing it again picks up changes to the theme. bussola only reads these folders, and only the theme files the extensions declare.

**Theme colors** lists every color of the current theme by area (text and background, borders, accents and states, diff, syntax) with a color picker and a hex field. Changes show at once, also in a small preview, and are kept on top of the theme: **Reset** next to a color, or **Reset all colors**, goes back to the theme's own colors. A warning appears when text on the background falls below the WCAG AA contrast of 4.5:1. **Export as VS Code theme** saves the current colors, your changes included, as a VS Code color theme `.json` that bussola or VS Code can import.

Only colors are read from an imported file: hex (`#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa`) and `rgb()` / `rgba()` values. Anything else, such as names, fonts or font styles, is ignored, so a theme cannot add CSS or scripts. Themes and changes are kept in this browser's local storage and never sent anywhere.

Each bussola color takes the first VS Code color listed for it that the theme sets. Syntax colors look up each TextMate scope listed, in order, among the theme's `tokenColors`, with prefix matching like VS Code: a rule for `keyword` colors `keyword.control`, and the most specific rule wins (the later one on a tie). The table lives in [`frontend/src/settings/themeMapping.ts`](frontend/src/settings/themeMapping.ts).

| Color | Variable | VS Code colors or TextMate scopes |
| --- | --- | --- |
| Text | `--text` | `editor.foreground`, `foreground` |
| Secondary text | `--muted` | `descriptionForeground`, `tab.inactiveForeground` |
| Faint text | `--faint` | `editorLineNumber.foreground`, `disabledForeground` |
| Background | `--bg` | `editor.background` |
| Panel background | `--bg-subtle` | `sideBar.background`, `editorWidget.background` |
| Sunken background | `--bg-sunken` | `editorGroupHeader.tabsBackground`, `input.background` |
| Border | `--border` | `panel.border`, `editorGroup.border`, `sideBar.border` |
| Strong border | `--border-strong` | `input.border`, `editorWidget.border`, `contrastBorder` |
| Focus ring | `--focus` | `focusBorder` |
| Accent and links | `--accent` | `textLink.foreground`, `button.background`, `badge.background` |
| Text on accent | `--accent-text` | `button.foreground`, `badge.foreground` |
| Approved and success | `--sea` | `gitDecoration.addedResourceForeground`, `terminal.ansiGreen` |
| Approved, moved | `--sea-soft` | `editorGutter.addedBackground` |
| Changed and warning | `--amber` | `editorWarning.foreground`, `list.warningForeground` |
| Partly approved | `--amber-soft` | `editorGutter.modifiedBackground` |
| Removed and error | `--danger` | `editorError.foreground`, `errorForeground` |
| Progress track | `--track` | `scrollbarSlider.background` |
| Added line | `--diff-insert` | `diffEditor.insertedLineBackground` |
| Removed line | `--diff-delete` | `diffEditor.removedLineBackground` |
| Added words | `--diff-insert-word` | `diffEditor.insertedTextBackground` |
| Removed words | `--diff-delete-word` | `diffEditor.removedTextBackground` |
| Added line number | `--diff-insert-gutter` | `diffEditorGutter.insertedLineBackground` |
| Removed line number | `--diff-delete-gutter` | `diffEditorGutter.removedLineBackground` |
| Highlighted line | `--diff-selected` | `editor.lineHighlightBackground`, `editor.rangeHighlightBackground` |
| Selected text | `--diff-selection` | `editor.selectionBackground` |
| Keywords | `--hl-keyword` | `keyword.control`, `storage.type` |
| Strings | `--hl-string` | `string.quoted.double` |
| Functions and types | `--hl-title` | `entity.name.function`, `support.function`, `entity.name.type` |
| Numbers and constants | `--hl-constant` | `constant.numeric`, `constant.language` |
| Tags and attributes | `--hl-tag` | `entity.name.tag`, `entity.other.attribute-name` |
| Properties and parameters | `--hl-property` | `variable.other.property`, `support.type.property-name`, `variable.parameter` |
| Comments | `--hl-comment` | `comment.line`, `comment.block` |
| Inserted text | `--hl-addition` | `markup.inserted` |
| Deleted text | `--hl-deletion` | `markup.deleted` |

Tinted backgrounds follow the color they belong to when the theme or your changes set it: the backgrounds of success, warning, error and info states, approved rows, the highlighted line number, and comments (from **Secondary text** when the theme has no comment color).

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

## AI providers

AI features are optional and off until you choose a provider. With a provider you get [AI descriptions](#ai-descriptions), the [AI impact rating](#ai-impact-rating) and the [AI review](#ai-review) of a pull request, and every AI action follows the rules below. bussola talks to one of three providers, set in the `[ai]` section of your user configuration, `config.toml` in `platformdirs.user_config_dir("bussola")` (on macOS `~/Library/Application Support/bussola/config.toml`, on Linux `~/.config/bussola/config.toml`; set `BUSSOLA_CONFIG_DIR` to use another directory). Choose the provider in **AI provider** under **AI** in **Settings**: pick Claude Code, the Anthropic API or an OpenAI-compatible endpoint, fill in the model, endpoint and key variable it asks for, and **Save** writes the `[ai]` section of `config.toml` for you, taking effect at once. You can also edit the file by hand; saving from **Settings** rewrites it, so comments in it are not kept. The panel then shows the active provider and model and a **Test connection** button that sends a short fixed prompt and no code.

**Claude Code CLI** runs the `claude` command already installed and signed in on your machine, so bussola needs no key:

```toml
[ai]
provider = "claude-code"
model = "claude-opus-5-5"  # optional, the command's default otherwise
```

bussola runs `claude -p` with JSON output, no tools, no saved session, safe mode (no hooks, plugins, skills or MCP servers from your Claude Code setup) and an empty temporary folder, so it cannot read or change your files. It needs a version of Claude Code that has `--safe-mode`; **Settings** tells you when yours is too old. `claude` signs in as it does when you run it yourself: with your Claude account, or with `ANTHROPIC_API_KEY` if that is set in the environment bussola runs in. bussola's own `BUSSOLA_*` variables, such as the session token, are not passed to it.

**Anthropic API** reads the key from the `ANTHROPIC_API_KEY` environment variable. `endpoint` defaults to `https://api.anthropic.com`; if you set it (for a gateway), give the base address without `/v1`:

```toml
[ai]
provider = "anthropic"
model = "claude-opus-5-5"  # the default
```

**OpenAI-compatible endpoint** covers Ollama, LM Studio, vLLM and similar local servers, and hosted services with the same API. The key is optional: set `api_key_env` to the environment variable that holds it, and bussola sends it as a bearer token. The answer length is capped with `max_completion_tokens`; servers that do not know it ignore it:

```toml
[ai]
provider = "openai-compatible"
endpoint = "http://localhost:11434/v1"  # Ollama; LM Studio uses http://localhost:1234/v1
model = "qwen2.5-coder"
```

Other options: `timeout` (seconds per request, default 600, at most 3600) and `api_key_env` (the name of the environment variable that holds the key, for example `api_key_env = "WORK_ANTHROPIC_KEY"`; the Anthropic API defaults to `ANTHROPIC_API_KEY`). Claude Code ignores `endpoint`. `max_tokens` sets the answer budget for the Anthropic API and OpenAI-compatible endpoints (default 16000), for example `max_tokens = 4000` for a local model with a small context window or more for long answers. `max_code_characters` caps the code sent in one **AI review** or **Rate impact** call (**Code per call** in **Settings**): without it the whole pull request goes in one call with Claude Code and the Anthropic API, whose models read up to a million tokens, and in calls of 100,000 characters with an OpenAI-compatible endpoint; set it for a model with a smaller context, and a larger pull request is split into several calls. Busy answers (HTTP 429 and 5xx) are retried twice, after the delay the server asks for, as long as that fits in the timeout. Requests to `localhost` and other loopback addresses never go through an HTTP proxy, and **Test connection** waits at most two minutes.

Keys are read only from environment variables. bussola never writes them to the database or to a configuration file, and `api_key` is not an accepted option.

Only your own configuration chooses the provider, model and endpoint. A repository can only turn AI off, with `provider = "none"` in the `[ai]` section of its `.bussola.toml`, for example for a confidential project; any other setting there is reported as a mistake, turns AI off for that repository and shows the reason on its AI buttons, while reviews keep working. A repository cannot turn AI on when you have not chosen a provider. This limit exists because `.bussola.toml` comes with the clone: a repository you review, or a pull request you open in bussola, must not be able to send your code or your key somewhere else, or spend your credit on a provider or model you did not choose.

### AI descriptions

With a provider configured, each unit card has a **Describe** button. One request to the provider explains what the unit does and what this change does to it, and rates the impact of the change as Low, Medium or High with a one-line reason. The answer appears above the diff in a collapsible block, rendered as Markdown and labelled as AI generated with the provider and model. When it mentions a specific change it links to the line: clicking the link scrolls the diff to that line and highlights it. While it runs the card shows that it is working and a **Cancel** button; a failure is shown on the card and **Describe** stays available.

Descriptions are kept per review for each version of a unit, so they are there when you open the review again. When a new revision changes a unit, its description is marked **outdated** until you press **Regenerate**; units that did not change keep theirs, also when their file is renamed. **Regenerate** asks the provider again and replaces the description. Binary files cannot be described.

### AI impact rating

The impact rating shows on the unit card as a **Low**, **Medium** or **High impact** badge, with its one-line reason in the tooltip. **Rate impact** on the review page rates every unit that has no current rating in a single request, or a few when `max_code_characters` is set and the pull request is larger, skipping units already rated or described; the badges appear as each request answers, a unit the model leaves out is reported as not rated, and **Cancel** stops the batch and keeps what was rated. Once units are rated, the unit controls can show only units of one impact (or the ones not rated yet) and order the units with the highest impact first. Ratings are kept per unit version like descriptions: when a new revision changes a unit its badge is marked outdated, and the next **Rate impact** or **Describe** rates it again.

### AI review

**AI review** on the review page reviews the whole pull request in one call: it sends every changed unit together, whole, with the pull request description, the list of every unit the pull request changes and the comments already made, so the model sees how the changes fit together and does not raise a point again. The same answer rates the impact of each unit it reviews, so the badges of units without a rating appear when the review ends, with no separate rating step first. With `max_code_characters` set, a larger pull request is sent in a few parts of at most that size, the highest impact first for units already rated, and each part still lists the rest.

While it reviews, the model can follow the code the way you would in an editor, with read-only tools on the two reviewed commits: where a name is defined and where it is used (the same lookup as Cmd+click, so a language server is used when one is installed), any lines of any file, a text search over the repository, and the diff of any other changed unit. That is how it finds a caller left behind by a changed signature or return value, even in a file the pull request does not touch. Files that `.bussola.toml` excludes from reviews stay out of reach, and each part of the review can use at most 40 tools. The tools work with all three providers: the Anthropic API and OpenAI-compatible endpoints call them directly, and Claude Code reaches them through an MCP server that bussola starts on `127.0.0.1` for that call only, under an address nobody else knows; Claude Code then keeps your user settings, so it signs in and picks its model as for the other AI actions, but runs without hooks, CLAUDE.md files, slash commands, other MCP servers and its own tools, with only the bussola tools allowed. A local server whose model does not support tool calls may refuse the request, and the review page then shows its error.

Each problem it finds becomes a thread anchored to its lines, like one you write: it shows an **AI** badge and the provider and model as its author, and you can reply to it, resolve it or delete it. The comment starts with the severity (🔴 Critical, 🟠 High, 🟡 Medium or 🔵 Low) and a one-line title, followed by what is wrong, why it matters and a **Fix:** paragraph, and the most severe findings are added first. The model is asked to anchor a problem at the change that causes it and to name other places in the text; a finding goes to the changed unit that has its line (for a renamed file, under its new or its old name), one outside the changed units lands on the nearest unit of the same file, or, for a file the pull request does not change, becomes a comment on the whole review that names the place. One that repeats an existing thread on the same line is dropped, and one too long for a comment is shortened.

While it runs the review page shows how many units are done out of the total and how many times the model looked up code, also in another tab or after a reload, and **Cancel** stops it from any of them, keeping the threads already added. Each unit is remembered once reviewed, so running **AI review** again, for example after new commits, reviews only the units that changed since their last AI review, with the rest of the pull request still listed and reachable through the tools; the page shows how many units already have one. **Details** opens what each run did: the model's summary, a one-sentence verdict followed by a short list of what it checked and what it found, with links to the lines it mentions (a click closes **Details** and scrolls the review to the line, highlighted, or opens the file when it is not part of the review), the findings with their place (a click opens the thread), every code lookup with its arguments and result, the units reviewed with their impact, and any error; earlier runs can be picked from a list, also while a run is still going. **Review again** reviews the whole pull request once more, also the units already reviewed, for example after switching model or after a change to how bussola reviews; the threads it added before stay and are given to the model, so it does not repeat them. When only some units have an AI review, the two buttons say how many units they send, such as **Review 12 units** for the ones without one and **Review all 21** for the whole pull request. AI threads follow new revisions like any other thread. **Sync** sends them to GitHub like your comments, each with a last line saying it was generated by the bussola AI review and naming the provider and model.

### AI prompts

**AI prompts** in **Settings** lets you change what the model is told to do for **Describe**, **Rate impact** and **AI review**, for example to focus on security or to write in another language. bussola always keeps its own part of each prompt, which says what the model gets, never to follow instructions written in the code, which tools it has and the format of the answer; your instructions come after it and replace bussola's default ones, which each prompt shows until you change it. **Reset to default** brings a prompt back, and **Save prompts** writes the changed ones to the `[ai.prompts]` section of your `config.toml` (keys `describe`, `impact` and `review`), which you can also edit by hand. A repository's `.bussola.toml` cannot change them. Cached answers follow the prompt, so a changed prompt asks the model again.

### What leaves your machine

- Nothing, while no provider is configured.
- Code is sent only when you start an AI action, and only the code that action works on. The AI review also sends the pull request title and description, the comments made on it, and what the model reads with its tools: other lines and files of the repository at the reviewed commits, except the files `.bussola.toml` excludes from reviews. The first time an action would send code to a provider, model and endpoint, bussola names them and waits for **Send code**; the choice is kept in that browser.
- With Claude Code or the Anthropic API, the code goes to Anthropic under the terms of your account. With an OpenAI-compatible endpoint, it goes only to the address you configured, which stays on your machine for a local server.
- Answers are checked against the format each action expects, and a clear error is shown when the model returns something unusable. Each request has a timeout and can be cancelled.
- Results are cached in the local database by the content hash of what was sent, the prompt version, the model and the endpoint, so unchanged code is not sent again. With Claude Code and no `model` set, the model actually used is not known, so nothing is cached. Set `model` to a full model ID rather than an alias such as `opus`, so that cached results follow the model you use.

## Data

Reviews, approvals and comments are stored in SQLite at `platformdirs.user_data_dir("bussola")/bussola.db` (on macOS `~/Library/Application Support/bussola`). Set `BUSSOLA_DATA_DIR` to use another directory. Language servers run on copies of reviewed commits in its `checkouts` folder, which is removed when bussola stops.

A registered repository is remembered by its path and its first commit. If you move it, add it again from the new location and its reviews follow.

## Security

The server is meant for one person on one machine.

- **Network:** it listens on `127.0.0.1` by default and warns if you pass another `--host`.
- **Session token:** every API call needs the session token cookie (HttpOnly, SameSite=Strict, one per port, so two servers do not log each other out).
- **Host check:** requests whose `Host` header is not `127.0.0.1:<port>`, `localhost:<port>`, `[::1]:<port>` or the `--host` you passed are rejected, which blocks DNS rebinding.
- **Git refs and files:** refs are validated with `git rev-parse --verify --end-of-options` before use. File contents are read only from the git object database.
- **bussola:// links:** a link chooses what to open. Like **Open pull request**, opening a pull request link fetches it with `git fetch` into `refs/bussola/pull/<number>` and starts its review if there is none. Its parameters are validated (repository name, numbers, a relative file path, a thread or comment id), anything else in it is ignored, and no link approves, resolves, sends or deletes anything.
- **Opening links:** GitHub links are opened by the server in your default browser, as a new tab, so they work even when the bussola page runs in an app-style window. The server only opens `https://github.com` addresses.
- **Outbound traffic:** the only network access is `git fetch` when you ask for it (including by opening a pull request link), `gh` when you sync or have a pull request review open, downloads of images attached on GitHub shown in comments and descriptions, and requests to the AI provider you configured, only when you start an AI action or test the connection (see [AI providers](#ai-providers)). Language servers are started with downloads turned off (`GOPROXY=off` for gopls, no automatic type acquisition for TypeScript).
- **Rendered Markdown:** HTML in comments and descriptions is sanitized with GitHub's rules before it is shown. Attached images are served from `/api/forge/asset` only for `https://github.com/.../assets/...` links and only when they are images, with a sandboxing Content-Security-Policy.

## Status

bussola is used on real pull requests, but it is young. Until 1.0, commands, options and the UI may change between minor versions. Your data is kept across upgrades: the database is migrated automatically at startup, and a change to how files are split into units is applied to existing reviews at their next **Sync**, without losing approvals of units that did not change.

## FAQ

<details><summary><b>Does my code leave my machine?</b></summary>

No. bussola reads your local clone. It only talks to your git remote when you sync, and to GitHub through your own `gh` login when you use the pull request features. If you configure an AI provider, the code of an AI action goes to that provider when you start the action; see [What leaves your machine](#what-leaves-your-machine).
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
