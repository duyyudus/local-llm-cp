from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="Local LLM control panel backend.", no_args_is_help=True)
server_app = typer.Typer(help="Run the API server.", no_args_is_help=True)
app.add_typer(server_app, name="server")


def _upgrade_database() -> None:
    from alembic.config import Config

    from alembic import command

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")


@app.command("migrate")
def migrate() -> None:
    """Apply database migrations."""
    _upgrade_database()
    typer.echo("Database is up to date.")


@server_app.command("start")
def start_server(
    host: str = typer.Option("0.0.0.0", help="Bind socket to this host"),
    port: int = typer.Option(8000, help="Bind socket to this port"),
    reload: bool = typer.Option(False, help="Enable auto-reload on code change"),
    migrate: bool = typer.Option(True, help="Apply database migrations before starting"),
) -> None:
    """Start the FastAPI application server."""
    import uvicorn

    if migrate:
        _upgrade_database()
    typer.echo(f"Starting API server on {host}:{port}...")
    # Log and GPU streams live in process memory, so this must stay a single worker.
    uvicorn.run("api_server.app.main:app", host=host, port=port, reload=reload)
