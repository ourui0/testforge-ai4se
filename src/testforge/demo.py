"""Public demo mode — closed fixture registry, no external code or credentials."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class DemoTaskRequest(BaseModel):
    """Only a pre-defined scenario name is accepted — no URLs, no keys."""

    model_config = ConfigDict(extra="forbid")

    scenario: str = "weak-then-strong"


class DisabledCredentialStore:
    """Credentials are disabled in public demo mode."""

    def get(self, provider: str, allow_dotenv: bool = False) -> str:
        raise RuntimeError("credentials are disabled in public demo mode")

    def set(self, provider: str, secret: str) -> None:
        raise RuntimeError("credentials are disabled in public demo mode")

    def status(self, provider: str) -> Any:
        from unittest.mock import MagicMock
        s = MagicMock()
        s.configured = False
        s.source = None
        return s

    def clear(self, provider: str) -> None:
        pass


class DemoScenario:
    """Pre-recorded, deterministic scenario data."""

    def __init__(self, name: str, data: dict[str, Any]) -> None:
        self.name = name
        self.responses: list[Any] = data.get("responses", [])
        self.tool_results: list[Any] = data.get("tool_results", [])


class DemoApplicationFactory:
    """Create ApplicationService instances from bundled demo fixtures."""

    def __init__(self, fixture_dir: Path | None = None) -> None:
        if fixture_dir is None:
            fixture_dir = (
                Path(__file__).resolve().parents[3]
                / "tests"
                / "fixtures"
                / "demo"
            )
        self._registry: dict[str, DemoScenario] = {}
        self._load(fixture_dir)

    def _load(self, directory: Path) -> None:
        if not directory.is_dir():
            return
        for path in sorted(directory.glob("*.json")):
            scenario_name = path.stem
            data = json.loads(path.read_text(encoding="utf-8"))
            self._registry[scenario_name] = DemoScenario(scenario_name, data)

    def create(self, scenario: str) -> Any:
        if scenario not in self._registry:
            raise ValueError(f"unknown demo scenario: {scenario}")
        fixture = self._registry[scenario]
        # Return a dict with enough shape for demo routes to consume
        return {
            "scenario": fixture.name,
            "responses": fixture.responses,
            "tool_results": fixture.tool_results,
        }
