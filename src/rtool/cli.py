import threading
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from rtool.app import create_app
from rtool.config import DEFAULT_HOST, DEFAULT_PORT, load_repo_config
from rtool.git import GitError, GitRepo, InvalidRefError
from rtool.review.refs import NoBaseBranchError, default_base_ref, resolve_review_commits
from rtool.review.scope import compute_scope
from rtool.units.extract import FileUnitExtractor

BROWSER_OPEN_DELAY_SECONDS = 1.0
USAGE_ERROR_EXIT_CODE = 2

app = typer.Typer(no_args_is_help=True, add_completion=False)

RepoOption = Annotated[Path | None, typer.Option("--repo", help="Repository path (default: current directory)")]
BaseOption = Annotated[str | None, typer.Option("--base", help="Base branch (default: from .rtool.toml, then develop, main, master)")]


@app.callback()
def root() -> None:
    """Local, per-function code review on git branches."""


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Interface to bind")] = DEFAULT_HOST,
    port: Annotated[int, typer.Option(help="Port to listen on")] = DEFAULT_PORT,
    no_open: Annotated[bool, typer.Option("--no-open", help="Do not open the browser")] = False,
) -> None:
    """Start the review UI."""
    url = f"http://{host}:{port}/"
    if not no_open:
        threading.Timer(BROWSER_OPEN_DELAY_SECONDS, webbrowser.open, args=[url]).start()
    typer.echo(f"rtool listening on {url}")
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


@app.command()
def status(head: Annotated[str, typer.Argument(help="Branch or commit under review")], base: BaseOption = None, repo: RepoOption = None) -> None:
    """Print the units changed by HEAD against its base."""
    try:
        git_repo = GitRepo.discover(repo or Path.cwd())
        config = load_repo_config(git_repo.root)
        commits = resolve_review_commits(git_repo, head, base or default_base_ref(git_repo, config))
        changes = compute_scope(git_repo, commits.merge_base_sha, commits.head_sha, FileUnitExtractor(config))
    except (GitError, InvalidRefError, NoBaseBranchError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(USAGE_ERROR_EXIT_CODE) from error
    for change in changes:
        typer.echo(f"{change.change_type:<9}{change.key.kind:<9}{change.key}")


def main() -> None:
    app()
