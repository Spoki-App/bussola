# Contributing

Thanks for helping with rtool. Bug reports, ideas and pull requests are welcome. For a larger change, open an issue first so we can agree on the approach.

## Principles

Every change should keep rtool:

- **Local:** your code never leaves your machine. Network access is `git fetch` and `gh`, and only when the user asks for it or has a pull request review open.
- **Content-based:** approvals and threads follow code by its content, not by commit or line number.
- **Quiet:** nothing is written to the repository, its branches or GitHub without an explicit action.
- **Small:** few dependencies, one process, one SQLite file.

If a change trades one of these for something else, say so in the pull request.

## Layout

| Path | What |
|---|---|
| `src/rtool/cli.py`, `app.py` | Command line and the FastAPI app |
| `src/rtool/units/` | Splitting files into units: tree-sitter extractors, normalization, hashing |
| `src/rtool/review/` | Revisions, unit states, approvals, threads and their anchoring |
| `src/rtool/forge/` | GitHub through `gh`: pull requests, importing and sending comments |
| `src/rtool/git/` | Running `git` safely |
| `src/rtool/storage/` | SQLAlchemy models, repositories and Alembic migrations |
| `src/rtool/api/` | HTTP routes and schemas |
| `frontend/` | React UI, built into `src/rtool/static/` |
| `tests/` | Backend tests; `tests/fakegh` is the fake `gh` used by the GitHub tests |
| `docs/design.md` | The rules behind units, approvals, threads and GitHub sync |

## Setup

You need Python 3.12+, [uv](https://docs.astral.sh/uv/), git and Node.js 22.12+ (`frontend/.nvmrc` pins 24).

```bash
uv sync
npm --prefix frontend ci
uv run rtool serve --no-open
npm --prefix frontend run dev
```

The Vite dev server proxies `/api` to `127.0.0.1:8765`. To get the session cookie on the Vite origin, open `http://localhost:5173/api/health?token=<token>` once, using the token printed by `rtool serve` (set `RTOOL_TOKEN` to keep the same token across restarts, and `RTOOL_DATA_DIR` to keep development data apart from your own reviews).

## Checks

Run these before opening a pull request; CI runs the same ones.

```bash
uv run ruff format --check . && uv run ruff check . && uv run basedpyright && uv run pytest
npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend test
npm --prefix frontend run build && npm --prefix frontend run e2e
```

The Playwright smoke test needs a browser once: `npx --prefix frontend playwright install chromium`. The GitHub tests use a fake `gh` from `tests/fakegh` and make no network calls.

## Database migrations

Migrations live in `src/rtool/storage/migrations` and run automatically at startup. After changing `src/rtool/storage/models.py`:

```bash
uv run alembic -c alembic.ini upgrade head
uv run alembic -c alembic.ini revision --autogenerate -m "describe the change"
rm dev.db
```

## Style

- Match the code around your change: naming, structure and the small-function style.
- Prefer self-explanatory names over comments.
- Every behaviour change comes with a test. Backend tests go through the HTTP API where possible (`tests/apiclient.py`).
- Update the [README](README.md) when user-visible behaviour changes, and [docs/design.md](docs/design.md) when the rules behind it change.
- Add a line under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md).
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org) (`feat:`, `fix:`, `perf:`, `refactor:`, `docs:`, `test:`, `chore:`).
- English, short sentences, and no em dash characters (a test checks).

## Releases (maintainers)

`scripts/release.sh X.Y.Z` on a clean `main` sets the package version, moves the `## [Unreleased]` notes under the new version, commits, tags `vX.Y.Z` and pushes. The Release workflow then builds the UI and the package, publishes it to PyPI and creates the GitHub release with the same notes.

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
