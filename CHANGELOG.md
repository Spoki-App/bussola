# Changelog

All notable changes to bussola are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org).

## [Unreleased]

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
