# Changelog

All notable changes to bussola are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org).

## [Unreleased]

### Added

- While Cmd (Ctrl on Linux and Windows) is held, the name under the pointer is underlined, with a pointer cursor, when Cmd+click can take you somewhere, in the diff and in the window showing a file outside the review. Keywords, strings, comments, punctuation and names with no result are never underlined, and the underline goes as soon as the key is released or the pointer leaves the code. Each name is checked once, after the pointer rests on it ([#40](https://github.com/Spoki-App/bussola/issues/40)).
- AI impact rating of each unit: a **Low**, **Medium** or **High impact** badge on the unit card with its one-line reason in the tooltip, marked outdated when a new revision changes the unit. **Rate impact** on the review page rates every unit without a current rating in one batch and can be cancelled, keeping what was rated. The units can be filtered by impact and ordered with the highest impact first ([#18](https://github.com/Spoki-App/bussola/issues/18)).
- The window and tab title names the open review: `<project>#<number> <title>` for a pull request, such as `bussola#34 feat: AI description and impact rating of a unit, on demand`, and `<project> <branch>` for a branch. It follows the pull request title after a sync, and other pages keep `bussola` ([#50](https://github.com/Spoki-App/bussola/issues/50)).
- The AI provider can be chosen in **Settings**: provider, model, endpoint, key variable, timeout and answer budget are saved to the `[ai]` section of `config.toml` and take effect at once. Keys still come only from environment variables, and **Settings** saves only the name of the variable.
- **Describe** on each unit card asks the AI provider, in one call, what the unit does, what the change does to it and how much impact the change has (Low, Medium or High, with a one-line reason). The description is shown above the diff as Markdown, labelled with the provider and model, kept per unit version, marked outdated when a new revision changes the unit, and can be regenerated or cancelled while it runs ([#17](https://github.com/Spoki-App/bussola/issues/17)).
- The header of an open unit stays visible below the file header while you scroll through its diff, so its name and **Approve** stay at hand.
- Pluggable AI provider for the upcoming AI features: Claude Code CLI, Anthropic API or an OpenAI-compatible endpoint (Ollama, LM Studio), chosen in the `[ai]` section of the user configuration. A repository's `.bussola.toml` can only turn AI off; it can never turn AI on or choose where code is sent, because it arrives with the clone. Keys come only from environment variables. **Settings** shows the active provider and model and can test the connection. The building blocks for the AI actions are in place: an action button that stays hidden until a provider is configured and names the provider before code is first sent, schema-validated answers, timeouts and cancellation, batches with progress, and a result cache keyed by content hash, prompt version, system prompt and schema, and model ([#16](https://github.com/Spoki-App/bussola/issues/16)).
- Go to definition and find usages with Cmd+click (Ctrl+click on Linux and Windows) for Python, TypeScript/TSX, JavaScript and Go: a single result in the review scrolls to its line, others open in a list and, outside the review, in a window showing the file at the reviewed commit. A tree-sitter index of the repository works with nothing installed, and basedpyright, pyright, typescript-language-server or gopls are used when found on `PATH` ([#13](https://github.com/Spoki-App/bussola/issues/13)).
- Diff layout setting: split, unified or automatic, in **Settings** and in the review bar. Automatic splits units that rewrite lines when the window is at least as wide as a threshold set in **Settings** ([#10](https://github.com/Spoki-App/bussola/issues/10)).
- Changed words inside a modified line are highlighted with a stronger background on both the removed and the added line, when the two lines are similar enough ([#25](https://github.com/Spoki-App/bussola/issues/25)).
- Long lines in the diff wrap with a hanging indent and one line number per source line. Wrapping is on by default and can be turned off in Settings or with the wrap icon that appears at the bottom right of an open unit under the mouse; without wrapping, long lines stay on one row and the diff scrolls sideways, in split view each side on its own with its own scroll bar so the old and new lines stay aligned ([#11](https://github.com/Spoki-App/bussola/issues/11)).
- **Sync** marks as viewed on GitHub the files whose changes you have all approved. Partly approved files and files changed since approval are left alone, files already viewed are not touched, and a file that cannot be marked does not fail the sync ([#26](https://github.com/Spoki-App/bussola/issues/26)).
- `bussola://` links open the home page, a pull request review (started if needed), a file and line, highlighted, or a thread. In a pull request review, link icons copy a link to the review, a unit, a thread or, on hover, any line of the new version. A GitHub pull request link with `https` replaced by `bussola` works too. `bussola install-handler` registers the scheme on macOS, Linux and Windows, and a link starts the server when it is not running ([#20](https://github.com/Spoki-App/bussola/issues/20)).
- Unit names in card headers, methods included, and in the conversation panel start with their module (Python dotted module, TypeScript/JavaScript file path, Go package import path), muted, with the unit's own name in bold; long titles are cut at the start so the name stays visible, and a new box on the review page finds units by module, name or path ([#15](https://github.com/Spoki-App/bussola/issues/15)).

### Changed

- Lines are matched ignoring spaces, so code moved into a new block stays next to its old version in split view, with only the indentation it gained or lost highlighted at the start of the line, instead of showing as a block removed and a different block added. In such a block the lines added or removed with no counterpart are highlighted in full.
- Cmd+click with a single result outside the review opens the file in a window at once, instead of a list with one entry.
- The unit filter (All, To review, Since my last review) is kept in this browser, so a reload or a new tab opens with the last choice, as the diff layout already did.
- The unit filter, the search box and the diff layout switch sit at the top of the **Files** bar, so they stay visible while you scroll the units. With the **Files** bar hidden they are above the units.
- Allow tree-sitter 0.26. Syntax tree positions are read as plain tuples, because the `Point.row` and `Point.column` properties in tree-sitter 0.26.0 drop a reference on every read and crash the process on files longer than 256 lines.

### Fixed

- Unit cards no longer scroll on their own when the mouse wheel is over them. The button that copies a link to a line stuck out one pixel below the last line, which gave each card a vertical scrollbar.
- Added and removed lines and changed words use the dark theme colors in dark mode. The light theme colors were applied instead and were hard to see.
- Text selected in the diff is readable in dark mode. It was shown on the light blue selection background of the light theme.
- **Approve file** no longer skips units whose content matches a unit already approved in another file, such as test classes with the same header. They were taken for approvals moved from that file and left as New.
- The first requests after starting with a new database no longer fail with a server error when several arrive at once and all try to add the same reviewer.
- Comments on the whole review, including pull request comments and review summaries imported from GitHub, no longer have a Resolve button and no longer count as open threads, as on GitHub.
- Expressions inside Python f-strings and JavaScript/TypeScript template literals are highlighted as code instead of string, with the braces, conversions and format specs set apart ([#21](https://github.com/Spoki-App/bussola/issues/21)).
- Below 700px wide, the Files list sits above the units again instead of covering the whole page, and unit headers wrap as intended. The narrow-screen styles were overridden by base rules declared after them.

## [0.1.0] - 2026-10-30

First public release.

### Added

- Local review UI (`bussola serve`) and the `bussola status` and `bussola refresh` commands.
- Changes split into functions, methods, classes, types, module-level code and whole files, with tree-sitter parsing for Python, TypeScript, TSX, JavaScript and Go.
- Approvals tied to unit content, kept across new commits, rebases and renames, and approval of selected lines in module-level code and whole files.
- "Since my last review" filter, revisions, and diffs from the approved version to the current one.
- Comment threads anchored to lines that follow the code across revisions, including resolved threads.
- GitHub pull request reviews through the `gh` CLI: listing, opening from a link, importing and syncing comments, sending comments as a pull request review, and resolving threads.
- GitHub-style rendering of comments and descriptions, with alerts, mermaid diagrams and attached images.
- Syntax highlighting, image diffs, a collapsible file tree and code font settings.
