import os
import threading
import webbrowser
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from bussola.access import TOKEN_ENV, allowed_hosts_for, is_local_host, new_token
from bussola.ai.config import default_config_file
from bussola.config import DEFAULT_HOST, DEFAULT_PORT, AppSettings, default_data_dir, load_repo_config
from bussola.errors import DomainError
from bussola.git import GitError, GitRepo, InvalidRefError
from bussola.handler import registration
from bussola.handler.opening import COMMAND, USAGE_ERROR_EXIT_CODE, open_link
from bussola.handler.server import ServerAddress
from bussola.handler.serving import run_published
from bussola.identity import GitConfigIdentity
from bussola.review.refs import NoBaseBranchError, default_base_ref

if TYPE_CHECKING:
    from bussola.review.context import ReviewContext

BROWSER_OPEN_DELAY_SECONDS = 1.0
SHORT_SHA_LENGTH = 12
CLI_ERRORS = (GitError, InvalidRefError, NoBaseBranchError, DomainError)

app = typer.Typer(no_args_is_help=True)


def complete_branch(ctx: typer.Context, incomplete: str) -> list[str]:
    try:
        local, remote = GitRepo(ctx.params.get("repo") or Path.cwd()).branches()
    except (GitError, OSError):
        return []
    return [name for name in (*local, *remote) if name.startswith(incomplete)]


RepoOption = Annotated[Path | None, typer.Option("--repo", help="Repository path (default: current directory)")]
BaseOption = Annotated[
    str | None, typer.Option("--base", help="Base branch (default: from .bussola.toml, then develop, main, master)", autocompletion=complete_branch)
]
HeadArgument = Annotated[str, typer.Argument(help="Branch or commit under review", autocompletion=complete_branch)]


@app.callback()
def root() -> None:
    """Local, per-function code review on git branches."""


@app.command()
def serve(
    repo: RepoOption = None,
    host: Annotated[str, typer.Option(help="Interface to bind")] = DEFAULT_HOST,
    port: Annotated[int, typer.Option(help="Port to listen on", min=1, max=65535)] = DEFAULT_PORT,
    no_open: Annotated[bool, typer.Option("--no-open", help="Do not open the browser")] = False,
    register: Annotated[bool, typer.Option("--register/--no-register", hidden=True)] = True,
) -> None:
    """Start the review UI."""
    host = host.removeprefix("[").removesuffix("]")
    if not is_local_host(host):
        typer.secho(f"warning: listening on {host} exposes your repositories to other machines on the network", fg=typer.colors.YELLOW, err=True)
    identity_dir = repo or Path.cwd()
    token = os.environ.pop(TOKEN_ENV, None) or new_token()
    settings = AppSettings(
        data_dir=default_data_dir().resolve(),
        identity_dir=identity_dir,
        token=token,
        allowed_hosts=allowed_hosts_for(host, port),
        port=port,
        config_file=default_config_file(),
    )
    if register:
        _register_if_repo(settings.data_dir, identity_dir)
    address = ServerAddress(host, port, token)
    url = address.reachable().url("/")
    if not no_open:
        threading.Timer(BROWSER_OPEN_DELAY_SECONDS, webbrowser.open, args=[url]).start()
    typer.echo(f"bussola listening on {url}")
    from bussola.app import create_app  # noqa: PLC0415

    run_published(create_app(settings), settings.data_dir, address)


app.command(COMMAND)(open_link)


@app.command("install-handler")
def install_handler() -> None:
    """Register bussola:// links with the operating system."""
    _apply_registration(
        lambda handler: handler.install, "bussola:// links now open bussola", "If anything was written, run `bussola uninstall-handler` to remove it."
    )


@app.command("uninstall-handler")
def uninstall_handler() -> None:
    """Remove the bussola:// link registration."""
    _apply_registration(lambda handler: handler.uninstall, "bussola:// links are no longer registered")


def _apply_registration(steps: Callable[[registration.Registration], Sequence[registration.Step]], done: str, on_failure: str = "") -> None:
    with _cli_errors():
        handler = registration.current_registration()
        try:
            registration.apply(steps(handler))
        except registration.HandlerError as error:
            raise registration.HandlerError("\n".join(filter(None, [str(error), on_failure]))) from error
    typer.echo(f"{done} ({handler.location})")


@app.command()
def status(head: HeadArgument, base: BaseOption = None, repo: RepoOption = None) -> None:
    """Refresh the review of HEAD and print the state of each changed unit."""
    from bussola.review.overview import unit_views  # noqa: PLC0415
    from bussola.review.revisions import refresh_review  # noqa: PLC0415

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
    from bussola.review.revisions import refresh_review  # noqa: PLC0415

    with _cli_errors(), _review_context(head, base, repo) as (context, git_repo):
        result = refresh_review(context.store, context.review, git_repo, fetch=fetch)
        units = len(context.store.reviews.snapshots(result.revision.id))
    outcome = "new" if result.created else "unchanged"
    revision = result.revision
    typer.echo(f"Revision {revision.number} ({outcome}): {revision.head_sha[:SHORT_SHA_LENGTH]} against {context.review.base_ref}, {units} units")


@contextmanager
def _review_context(head: str, base: str | None, repo_path: Path | None) -> Generator[tuple["ReviewContext", GitRepo]]:
    from bussola.review.context import ReviewContext  # noqa: PLC0415
    from bussola.review.repos import register_repo  # noqa: PLC0415
    from bussola.storage.database import Database  # noqa: PLC0415
    from bussola.storage.repositories import Store  # noqa: PLC0415

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
    from bussola.review.repos import register_repo  # noqa: PLC0415
    from bussola.storage.database import Database  # noqa: PLC0415
    from bussola.storage.repositories import Store  # noqa: PLC0415

    with Database.open(data_dir).session() as session:
        store = Store(session)
        register_repo(store, path)
        store.commit()


def main() -> None:
    app()
