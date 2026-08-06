"""Tests for TestForge CLI — Typer commands without credential leakage."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from testforge.cli import cli

# ── fixtures ─────────────────────────────────────────────────────────

class FakeApp:
    """Fake ApplicationService recording calls and returning test data."""

    def __init__(self) -> None:
        self.created_task = MagicMock()
        self.created_task.id = uuid4()
        self.project_image_builds: list[object] = []
        self._last_target: str | None = None
        self._sandbox_image = "testforge-project:abc123"

    def create_and_start(self, target_module: str) -> MagicMock:
        self._last_target = target_module
        return self.created_task

    def initialize_project(self, path: object, *, trusted_project: bool) -> MagicMock:
        self.project_image_builds.append((path, trusted_project))
        proj = MagicMock()
        proj.id = uuid4()
        proj.sandbox_image = self._sandbox_image
        return proj

    def get_task_status(self, task_id: object) -> str:
        return f"Task {task_id}: generating"


class FakeCredentials:
    """Fake credential store for CLI tests."""

    def __init__(self) -> None:
        self.set_calls: list[tuple[str, str]] = []
        self._secrets: dict[str, str] = {}

    def set(self, provider: str, secret: str) -> None:
        self.set_calls.append((provider, secret))
        self._secrets[provider] = secret

    def status(self, provider: str) -> MagicMock:
        s = MagicMock()
        s.configured = provider in self._secrets
        s.source = "keyring" if s.configured else None
        return s

    def get(self, provider: str) -> str:
        return self._secrets.get(provider, "")


@pytest.fixture
def app() -> FakeApp:
    return FakeApp()


@pytest.fixture
def credentials() -> FakeCredentials:
    return FakeCredentials()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _patch(monkeypatch: pytest.MonkeyPatch, app: FakeApp, creds: FakeCredentials) -> None:
    monkeypatch.setattr("testforge.cli.get_application", lambda: app)
    monkeypatch.setattr("testforge.cli.get_credentials", lambda: creds)


# ── run command (from brief) ─────────────────────────────────────────

def test_run_prints_task_id_without_secret(
    cli_runner: CliRunner, app: FakeApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run must print the task_id and never leak credentials."""
    monkeypatch.setattr("testforge.cli.get_application", lambda: app)
    result = cli_runner.invoke(cli, ["run", "src/calc.py"])
    assert result.exit_code == 0
    assert str(app.created_task.id) in result.stdout
    assert "sk-" not in result.stdout


# ── init command (from brief) ────────────────────────────────────────

def test_init_requires_explicit_trust(
    cli_runner: CliRunner, app: FakeApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """init must fail when user declines the trust prompt."""
    monkeypatch.setattr("testforge.cli.get_application", lambda: app)
    result = cli_runner.invoke(cli, ["init", "."], input="n\n")
    assert result.exit_code == 1
    assert app.project_image_builds == []


def test_init_builds_when_trusted(
    cli_runner: CliRunner, app: FakeApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """init must proceed when user confirms trust."""
    monkeypatch.setattr("testforge.cli.get_application", lambda: app)
    result = cli_runner.invoke(cli, ["init", "."], input="y\n")
    assert result.exit_code == 0
    assert len(app.project_image_builds) == 1


# ── status command ───────────────────────────────────────────────────

def test_status_shows_task_state(
    cli_runner: CliRunner, app: FakeApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """status must display the task's current state."""
    monkeypatch.setattr("testforge.cli.get_application", lambda: app)
    result = cli_runner.invoke(cli, ["status", str(app.created_task.id)])
    assert result.exit_code == 0
    assert "generating" in result.stdout.lower()


# ── credentials commands ─────────────────────────────────────────────

def test_credentials_status_shows_configured_without_secret(
    cli_runner: CliRunner, credentials: FakeCredentials, monkeypatch: pytest.MonkeyPatch
) -> None:
    """credentials status must show configured but never the secret."""
    credentials.set("openai", "sk-my-secret-key")
    monkeypatch.setattr("testforge.cli.get_credentials", lambda: credentials)
    result = cli_runner.invoke(cli, ["credentials", "status", "openai"])
    assert result.exit_code == 0
    assert "configured" in result.stdout.lower()
    assert "sk-my-secret-key" not in result.stdout


def test_credentials_set_stores_secret(
    cli_runner: CliRunner, credentials: FakeCredentials, monkeypatch: pytest.MonkeyPatch
) -> None:
    """credentials set must store via the credential store."""
    monkeypatch.setattr("testforge.cli.get_credentials", lambda: credentials)
    result = cli_runner.invoke(
        cli, ["credentials", "set", "openai"], input="sk-test-key\nsk-test-key\n"
    )
    assert result.exit_code == 0
    assert credentials.set_calls == [("openai", "sk-test-key")]


# ── reject command ───────────────────────────────────────────────────

def test_reject_requires_valid_uuid(cli_runner: CliRunner) -> None:
    """reject must fail on malformed UUID input."""
    result = cli_runner.invoke(cli, ["reject", "not-a-uuid"])
    assert result.exit_code != 0
