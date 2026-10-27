import threading
import webbrowser
from typing import Annotated

import typer
import uvicorn

from rtool.app import create_app
from rtool.config import DEFAULT_HOST, DEFAULT_PORT

BROWSER_OPEN_DELAY_SECONDS = 1.0

app = typer.Typer(no_args_is_help=True, add_completion=False)


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


def main() -> None:
    app()
