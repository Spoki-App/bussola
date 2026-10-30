# Changelog

All notable changes to bussola are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org).

## [Unreleased]

### Added

- Changed words inside a modified line are highlighted with a stronger background on both the removed and the added line, when the two lines are similar enough ([#25](https://github.com/Spoki-App/bussola/issues/25)).
- **Sync** marks as viewed on GitHub the files whose changes you have all approved. Partly approved files and files changed since approval are left alone, files already viewed are not touched, and a file that cannot be marked does not fail the sync ([#26](https://github.com/Spoki-App/bussola/issues/26)).

### Changed

- Allow tree-sitter 0.26. Syntax tree positions are read as plain tuples, because the `Point.row` and `Point.column` properties in tree-sitter 0.26.0 drop a reference on every read and crash the process on files longer than 256 lines.

### Fixed

- Comments on the whole review, including pull request comments and review summaries imported from GitHub, no longer have a Resolve button and no longer count as open threads, as on GitHub.
- Expressions inside Python f-strings and JavaScript/TypeScript template literals are highlighted as code instead of string, with the braces, conversions and format specs set apart ([#21](https://github.com/Spoki-App/bussola/issues/21)).

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
