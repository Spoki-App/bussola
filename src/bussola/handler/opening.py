import sys
from pathlib import Path
from typing import Annotated

import typer

from bussola.config import default_data_dir
from bussola.errors import DomainError
from bussola.handler.server import Launcher, record_link_error

USAGE_ERROR_EXIT_CODE = 2
COMMAND = "open-link"


def open_link(
    link: Annotated[str, typer.Argument(help="A bussola:// link")],
    data_dir: Annotated[Path | None, typer.Option("--data-dir", help="Data folder (default: BUSSOLA_DATA_DIR, then the user data folder)")] = None,
    search_path: Annotated[str | None, typer.Option("--search-path", hidden=True)] = None,
) -> None:
    """Open a bussola:// link, starting the server if it is not running."""
    data_dir = (data_dir or default_data_dir()).resolve()
    try:
        Launcher(data_dir, search_path=search_path).open(link)
    except Exception as error:
        record_link_error(data_dir, link, error)
        if isinstance(error, DomainError):
            typer.echo(f"error: {error}", err=True)
            raise typer.Exit(USAGE_ERROR_EXIT_CODE) from error
        raise


def main() -> None:
    link_app = typer.Typer(add_completion=False)
    link_app.command()(open_link)
    link_app(args=sys.argv[2:], prog_name=f"bussola {COMMAND}")
