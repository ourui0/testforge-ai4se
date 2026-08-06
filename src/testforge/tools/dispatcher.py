"""Domain tool dispatcher — discriminated requests, explicit handler registry."""

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from testforge.domain.errors import PolicyViolation


class ToolName(StrEnum):
    READ_SOURCE = "read_source"
    READ_TESTS = "read_tests"
    WRITE_TEST = "write_test"
    RUN_PYTEST = "run_pytest"
    MEASURE_COVERAGE = "measure_coverage"
    RUN_MUTATION = "run_mutation"
    REQUEST_REFACTOR_APPROVAL = "request_refactor_approval"
    APPLY_APPROVED_REFACTOR = "apply_approved_refactor"
    EXPORT_PATCH = "export_patch"


class ToolRequest(BaseModel):
    """Base discriminated request. tool string selects the handler."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: str


class RunPytestRequest(ToolRequest):
    """Run pytest with a fixed, hard-coded argument vector."""

    tool: str = ToolName.RUN_PYTEST


class ToolResult(BaseModel):
    """Result returned by every tool handler."""

    model_config = ConfigDict(frozen=True)

    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    content_hash: str | None = None
    audit_summary: str | None = None


_TOOL_REQUEST_ADAPTER: TypeAdapter[ToolRequest] = TypeAdapter(ToolRequest)

Handler = Callable[[ToolRequest], ToolResult]

_FIXED_PYTEST_ARGV = (
    "python",
    "-m",
    "pytest",
    "--json-report",
    "--json-report-file=/tmp/pytest.json",
    "-q",
)


class DomainToolDispatcher:
    """Dispatch validated ToolRequests to registered handlers.

    Unknown tools are rejected. Argument vectors are hard-coded in
    handlers — never built from user-controlled strings.
    """

    def __init__(self, sandbox: Any | None = None) -> None:
        self._sandbox = sandbox
        self._handlers: dict[ToolName, Handler] = {}
        self._register_defaults()

    def dispatch(self, request: ToolRequest) -> ToolResult:
        try:
            tool = ToolName(request.tool)
        except ValueError:
            raise PolicyViolation(
                f"unknown domain tool: {request.tool}"
            ) from None
        handler = self._handlers.get(tool)
        if handler is None:
            raise PolicyViolation(f"unknown domain tool: {request.tool}")
        return handler(request)

    def dispatch_raw(self, payload: dict[str, object]) -> ToolResult:
        try:
            request = _TOOL_REQUEST_ADAPTER.validate_python(payload)
        except ValidationError as exc:
            raise PolicyViolation(
                "unknown domain tool or invalid parameters"
            ) from exc
        return self.dispatch(request)

    # ── handlers ──────────────────────────────────────────────────

    def _register_defaults(self) -> None:
        self._handlers[ToolName.RUN_PYTEST] = self._handle_run_pytest

    def _handle_run_pytest(self, _request: ToolRequest) -> ToolResult:
        if self._sandbox is not None:
            result = self._sandbox.run(
                _FIXED_PYTEST_ARGV,
                workspace=getattr(self._sandbox, "_workspace", None),
                timeout_seconds=60,
            )
            return ToolResult(
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return ToolResult(exit_code=0, stdout="", stderr="")
