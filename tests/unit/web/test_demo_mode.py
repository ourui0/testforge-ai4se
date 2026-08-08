"""Tests for demo mode — no external code, no credentials, closed scenarios."""

import pytest
from fastapi.testclient import TestClient

from testforge.web.app import create_app


@pytest.fixture
def demo_client() -> TestClient:
    from unittest.mock import MagicMock
    app_mock = MagicMock()
    app_mock.create_demo_task.return_value = MagicMock(id="00000000-0000-0000-0000-000000000001")
    app = create_app(app_mock, demo_mode=True)
    return TestClient(app)


def test_demo_mode_rejects_repository_url_and_credentials(
    demo_client: TestClient,
) -> None:
    """Demo must reject upload URL and API key in request body."""
    response = demo_client.post(
        "/demo/tasks",
        json={
            "repository_url": "https://example.com/repo.git",
            "api_key": "sk-not-real",
        },
    )
    assert response.status_code == 422
    assert "repository_url" in response.text
    assert "api_key" in response.text


def test_demo_mode_allows_valid_scenario(demo_client: TestClient) -> None:
    """Valid scenario name must be accepted."""
    response = demo_client.post(
        "/demo/tasks", json={"scenario": "weak-then-strong"}
    )
    assert response.status_code == 200
    assert "task_id" in response.json()


def test_demo_routes_rejected_in_non_demo_mode() -> None:
    """Demo endpoints must return 403 when demo_mode=False."""
    from unittest.mock import MagicMock
    app_mock = MagicMock()
    app = create_app(app_mock, demo_mode=False)
    client = TestClient(app)
    response = client.post("/demo/tasks", json={"scenario": "weak-then-strong"})
    assert response.status_code == 403
