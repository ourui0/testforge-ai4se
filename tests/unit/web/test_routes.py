"""Tests for FastAPI WebUI routes — no secret leakage, CSRF protection."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from testforge.web.app import create_app

# ── fake application ─────────────────────────────────────────────────

class FakeApp:
    def __init__(self) -> None:
        self.task = MagicMock()
        self.task.id = uuid4()
        self.task.state = "generating"
        self.task.mutation_score = 75.0
        self.task.status_text = "Awaiting approval"
        self._known_ids: set[str] = {str(self.task.id)}

    def get_task_view(self, task_id: object) -> MagicMock:
        if str(task_id) not in self._known_ids:
            raise ValueError("task not found")
        return self.task

    def get_pending_approvals(self) -> list[MagicMock]:
        a = MagicMock()
        a.id = uuid4()
        a.kind = "refactor"
        return [a]

    def decide_approval(self, approval_id: object, *, approved: bool, actor: str) -> None:
        pass

    def create_demo_task(self, scenario: str) -> MagicMock:
        t = MagicMock()
        t.id = uuid4()
        return t

    def advance_demo_task(self, task_id: object) -> MagicMock:
        return self.task


@pytest.fixture
def fake_app() -> FakeApp:
    return FakeApp()


@pytest.fixture
def test_client(fake_app: FakeApp) -> TestClient:
    app = create_app(fake_app, demo_mode=False)
    return TestClient(app)


@pytest.fixture
def demo_client(fake_app: FakeApp) -> TestClient:
    app = create_app(fake_app, demo_mode=True)
    return TestClient(app)


# ── route tests (from brief) ─────────────────────────────────────────

def test_task_detail_shows_metrics_and_never_secret(
    test_client: TestClient, fake_app: FakeApp
) -> None:
    """Task detail must show metrics/status but never a credential."""
    response = test_client.get(f"/tasks/{fake_app.task.id}")
    assert response.status_code == 200
    assert "Mutation score" in response.text
    assert "Awaiting approval" in response.text
    assert "sk-example" not in response.text


def test_healthz_returns_ok(test_client: TestClient) -> None:
    """Health endpoint must return status ok."""
    response = test_client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_home_page_loads(test_client: TestClient) -> None:
    """Index page must return HTML."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert "TestForge" in response.text


def test_approval_page_shows_pending(test_client: TestClient) -> None:
    """Approvals page must list pending items."""
    response = test_client.get("/approvals")
    assert response.status_code == 200
    assert "Approve" in response.text


def test_reject_missing_task(test_client: TestClient) -> None:
    """404 on non-existent task."""
    response = test_client.get("/tasks/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_page_uses_aria_live(test_client: TestClient, fake_app: FakeApp) -> None:
    """Pages must include aria-live for accessibility."""
    response = test_client.get(f"/tasks/{fake_app.task.id}")
    assert 'aria-live="polite"' in response.text
