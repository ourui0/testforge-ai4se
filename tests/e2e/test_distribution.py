"""Distribution smoke tests — CLI entry point, health endpoint."""

from fastapi.testclient import TestClient

from testforge.web.app import create_app


def test_package_cli_help() -> None:
    """Installed package must expose testforge CLI entry point."""
    from testforge.cli import cli
    assert cli is not None
    # Verify cli is a Typer instance
    assert hasattr(cli, "registered_commands")


def test_cli_module_importable() -> None:
    """CLI module must be importable without errors."""
    import testforge.cli
    assert testforge.cli.cli is not None


def test_demo_health_endpoint() -> None:
    """Health endpoint must report demo mode."""
    from unittest.mock import MagicMock
    app = create_app(MagicMock(), demo_mode=True)
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["mode"] == "demo"
