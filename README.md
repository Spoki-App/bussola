# rtool

Local, per-function code review on git branches.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 22.12+ (see `frontend/.nvmrc`) to build the UI
- `git`

## Install

```bash
npm --prefix frontend ci
npm --prefix frontend run build
uv tool install .
rtool serve
```

The frontend build is written to `src/rtool/static/` and packaged with the Python wheel.

## Development

```bash
uv sync
uv run rtool serve --no-open
npm --prefix frontend run dev
```

The Vite dev server proxies `/api` to `127.0.0.1:8765`.

Checks:

```bash
uv run ruff format --check . && uv run ruff check . && uv run basedpyright && uv run pytest
npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend test
```
