"""TestForge CLI — Typer-based command-line interface."""

from pathlib import Path
from uuid import UUID

import typer

cli = typer.Typer(no_args_is_help=True)
credentials_cli = typer.Typer()
cli.add_typer(credentials_cli, name="credentials")


# ── application service access (patched in tests) ────────────────────


def get_application() -> object:
    """Return the singleton ApplicationService (replaced in tests)."""
    raise NotImplementedError("application not wired — use testforge.cli patching")


def get_credentials() -> object:
    """Return the singleton CredentialStore (replaced in tests)."""
    raise NotImplementedError("application not wired — use testforge.cli patching")


# ── top-level commands ───────────────────────────────────────────────


@cli.command()
def init(
    repository: str = typer.Argument(".", help="Path to the project repository"),
) -> None:
    trusted = typer.confirm(
        "This build may download dependencies and execute the project's "
        "build backend. Trust this repository?"
    )
    if not trusted:
        raise typer.Exit(code=1)
    project = get_application().initialize_project(
        Path(repository), trusted_project=True
    )
    typer.echo(f"initialized {project.id} with sandbox image {project.sandbox_image}")


@cli.command()
def run(
    target_module: str = typer.Argument(..., help="Target module path"),
) -> None:
    task = get_application().create_and_start(target_module)
    typer.echo(str(task.id))


@cli.command()
def status(
    task_id: str = typer.Argument(..., help="Task UUID"),
) -> None:
    state = get_application().get_task_status(UUID(task_id))
    typer.echo(state)


@cli.command()
def approve(
    approval_id: str = typer.Argument(..., help="Approval UUID"),
) -> None:
    get_application().approve(UUID(approval_id))
    typer.echo("approved")


@cli.command()
def reject(
    approval_id: str = typer.Argument(..., help="Approval UUID"),
) -> None:
    get_application().reject(UUID(approval_id))
    typer.echo("rejected")


@cli.command()
def apply(
    task_id: str = typer.Argument(..., help="Task UUID"),
) -> None:
    get_application().apply_patch(UUID(task_id))
    typer.echo("patch applied")


@cli.command()
def history(
    task_id: str = typer.Argument(..., help="Task UUID"),
) -> None:
    events = get_application().get_history(UUID(task_id))
    for event in events:
        typer.echo(str(event))


# ── credentials sub-commands ─────────────────────────────────────────


@credentials_cli.command("set")
def credential_set(
    provider: str = typer.Argument("openai", help="Provider name"),
) -> None:
    secret = typer.prompt(
        "API key", hide_input=True, confirmation_prompt=True
    )
    get_credentials().set(provider, secret)
    typer.echo(f"{provider} credential configured")


@credentials_cli.command("status")
def credential_status(
    provider: str = typer.Argument("openai", help="Provider name"),
) -> None:
    s = get_credentials().status(provider)
    typer.echo(
        f"provider: {provider}  configured: {s.configured}"
        f"  source: {s.source or 'none'}"
    )


@credentials_cli.command("clear")
def credential_clear(
    provider: str = typer.Argument("openai", help="Provider name"),
) -> None:
    get_credentials().clear(provider)
    typer.echo(f"{provider} credential cleared")


@cli.command()
def serve(port: int = 8000) -> None:
    typer.echo(f"starting server on port {port}...")
    get_application().serve(port)
