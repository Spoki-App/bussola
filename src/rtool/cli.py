import os
import threading
import webbrowser
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from rtool.app import create_app
from rtool.config import DEFAULT_HOST, DEFAULT_PORT, AppSettings, load_repo_config
from rtool.errors import DomainError
from rtool.git import GitError, GitRepo, InvalidRefError
from rtool.identity import GitConfigIdentity
from rtool.review.context import ReviewContext
from rtool.review.overview import unit_views
from rtool.review.refs import NoBaseBranchError, default_base_ref
from rtool.review.repos import register_repo
from rtool.review.revisions import refresh_review
from rtool.security import LOCAL_HOSTS, allowed_hosts_for, new_token
from rtool.storage.database import Database, default_data_dir
from rtool.storage.repositories import Store

BROWSER_OPEN_DELAY_SECONDS = 1.0
USAGE_ERROR_EXIT_CODE = 2
SHORT_SHA_LENGTH = 12
CLI_ERRORS = (GitError, InvalidRefError, NoBaseBranchError, DomainError)
TOKEN_ENV = "RTOOL_TOKEN"

app = typer.Typer(no_args_is_help=True, add_completion=False)

RepoOption = Annotated[Path | None, typer.Option("--repo", help="Repository path (default: current directory)")]
BaseOption = Annotated[str | None, typer.Option("--base", help="Base branch (default: from .rtool.toml, then develop, main, master)")]
HeadArgument = Annotated[str, typer.Argument(help="Branch or commit under review")]


@app.callback()
def root() -> None:
    """Local, per-function code review on git branches."""


@app.command()
def serve(
    repo: RepoOption = None,
    host: Annotated[str, typer.Option(help="Interface to bind")] = DEFAULT_HOST,
    port: Annotated[int, typer.Option(help="Port to listen on")] = DEFAULT_PORT,
    no_open: Annotated[bool, typer.Option("--no-open", help="Do not open the browser")] = False,
) -> None:
    """Start the review UI."""
    if host not in LOCAL_HOSTS:
        typer.secho(f"warning: listening on {host} exposes your repositories to other machines on the network", fg=typer.colors.YELLOW, err=True)
    identity_dir = repo or Path.cwd()
    token = os.environ.get(TOKEN_ENV) or new_token()
    settings = AppSettings(data_dir=default_data_dir(), identity_dir=identity_dir, token=token, allowed_hosts=allowed_hosts_for(host, port))
    _register_if_repo(settings.data_dir, identity_dir)
    url = f"http://{host}:{port}/?token={token}"
    if not no_open:
        threading.Timer(BROWSER_OPEN_DELAY_SECONDS, webbrowser.open, args=[url]).start()
    typer.echo(f"rtool listening on {url}")
    uvicorn.run(create_app(settings), host=host, port=port, log_level="warning")


@app.command()
def status(head: HeadArgument, base: BaseOption = None, repo: RepoOption = None) -> None:
    """Refresh the review of HEAD and print the state of each changed unit."""
    with _cli_errors(), _review_context(head, base, repo) as (context, git_repo):
        result = refresh_review(context.store, context.review, git_repo)
        views = unit_views(context, result.revision)
    for view in views:
        snapshot = view.snapshot
        name = f"{snapshot.path}::{snapshot.qualified_name}" if snapshot.qualified_name else snapshot.path
        typer.echo(f"{view.status.state:<16}{snapshot.kind:<9}{name}")


@app.command()
def refresh(
    head: HeadArgument,
    base: BaseOption = None,
    repo: RepoOption = None,
    fetch: Annotated[bool, typer.Option("--fetch", help="Run git fetch --prune first")] = False,
) -> None:
    """Record a new revision of the review of HEAD if any commit changed."""
    with _cli_errors(), _review_context(head, base, repo) as (context, git_repo):
        result = refresh_review(context.store, context.review, git_repo, fetch=fetch)
        units = len(context.store.reviews.snapshots(result.revision.id))
    outcome = "new" if result.created else "unchanged"
    revision = result.revision
    typer.echo(f"Revision {revision.number} ({outcome}): {revision.head_sha[:SHORT_SHA_LENGTH]} against {context.review.base_ref}, {units} units")


@contextmanager
def _review_context(head: str, base: str | None, repo_path: Path | None) -> Generator[tuple[ReviewContext, GitRepo]]:
    git_repo = GitRepo.discover(repo_path or Path.cwd())
    base_ref = base or default_base_ref(git_repo, load_repo_config(git_repo.root))
    git_repo.resolve_commit(head)
    git_repo.resolve_commit(base_ref)
    with Database.open(default_data_dir()).session() as session:
        store = Store(session)
        repo = register_repo(store, git_repo.root)
        review = store.reviews.find_or_add_review(repo.id, head, base_ref)
        identity = GitConfigIdentity(git_repo.root).current()
        yield ReviewContext(store, review, store.reviews.reviewer(identity.email, identity.name)), git_repo
        store.commit()


@contextmanager
def _cli_errors() -> Generator[None]:
    try:
        yield
    except CLI_ERRORS as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(USAGE_ERROR_EXIT_CODE) from error


def _register_if_repo(data_dir: Path, path: Path) -> None:
    try:
        GitRepo.discover(path)
    except GitError:
        return
    with Database.open(data_dir).session() as session:
        store = Store(session)
        register_repo(store, path)
        store.commit()


def main() -> None:
    app()
