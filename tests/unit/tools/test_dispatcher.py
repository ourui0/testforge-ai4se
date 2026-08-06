"""Tests for DomainToolDispatcher — discriminated requests and explicit registry."""

from unittest.mock import MagicMock

import pytest

from testforge.domain.errors import PolicyViolation
from testforge.tools.dispatcher import (
    DomainToolDispatcher,
    RunPytestRequest,
    ToolName,
    ToolRequest,
)

# ── helpers ──────────────────────────────────────────────────────────

@pytest.fixture
def sandbox() -> MagicMock:
    sb = MagicMock()
    sb.run.return_value.exit_code = 0
    sb.run.return_value.stdout = ""
    sb.run.return_value.stderr = ""
    return sb


@pytest.fixture
def dispatcher(sandbox: MagicMock) -> DomainToolDispatcher:
    return DomainToolDispatcher(sandbox=sandbox)


# ── unknown-tool rejection (from brief) ──────────────────────────────

def test_unknown_tool_is_rejected(dispatcher: DomainToolDispatcher) -> None:
    """Raw payload with unknown tool name must be rejected."""
    with pytest.raises(PolicyViolation, match="unknown domain tool"):
        dispatcher.dispatch_raw({"tool": "shell", "command": "rm -rf /"})


def test_malformed_payload_is_rejected(dispatcher: DomainToolDispatcher) -> None:
    """Payload missing required tool field must be rejected."""
    with pytest.raises(PolicyViolation):
        dispatcher.dispatch_raw({"not_a_tool_field": 123})


# ── pytest dispatch (from brief) ─────────────────────────────────────

def test_run_pytest_uses_fixed_argv(
    dispatcher: DomainToolDispatcher, sandbox: MagicMock
) -> None:
    """Pytest handler must use hard-coded argv, never user strings."""
    dispatcher.dispatch(RunPytestRequest())
    assert sandbox.run.call_args[0][0] == (
        "python",
        "-m",
        "pytest",
        "--json-report",
        "--json-report-file=/tmp/pytest.json",
        "-q",
    )


# ── unknown tool via typed dispatch ──────────────────────────────────

def test_dispatch_validates_against_registry(
    dispatcher: DomainToolDispatcher,
) -> None:
    """Direct dispatch of an unregistered request raises PolicyViolation."""
    fake_request = ToolRequest(tool="bogus_tool")
    with pytest.raises(PolicyViolation, match="unknown domain tool"):
        dispatcher.dispatch(fake_request)


# ── ToolName enum ────────────────────────────────────────────────────

def test_tool_name_has_required_members() -> None:
    """ToolName must define all 9 SPEC tools."""
    members = {m.value for m in ToolName}
    expected = {
        "read_source",
        "read_tests",
        "write_test",
        "run_pytest",
        "measure_coverage",
        "run_mutation",
        "request_refactor_approval",
        "apply_approved_refactor",
        "export_patch",
    }
    assert members == expected


# ── ToolRequest discriminator ────────────────────────────────────────

def test_run_pytest_request_has_no_freeform_args() -> None:
    """RunPytestRequest must not accept arbitrary command overrides."""
    req = RunPytestRequest()
    assert not hasattr(req, "command")
    assert not hasattr(req, "args")


def test_dispatch_raw_rejects_unknown_tool(dispatcher: DomainToolDispatcher) -> None:
    """dispatch_raw must reject payloads with unknown tool names."""
    with pytest.raises(PolicyViolation, match="unknown domain tool"):
        dispatcher.dispatch_raw({"tool": "not_a_real_tool"})


def test_dispatch_rejects_unregistered_tool(dispatcher: DomainToolDispatcher) -> None:
    """dispatch must reject even valid ToolName values that lack a handler."""
    req = ToolRequest(tool="read_source")  # valid name, no handler registered
    with pytest.raises(PolicyViolation, match="unknown domain tool"):
        dispatcher.dispatch(req)
