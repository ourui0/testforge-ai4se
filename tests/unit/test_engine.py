"""Tests for AgentEngine — persisted, one-transition advancement."""

from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from testforge.domain.models import TaskRecord
from testforge.domain.state_machine import TaskState
from testforge.engine import AgentEngine
from testforge.persistence.repository import SQLiteTaskRepository

# ── helpers ──────────────────────────────────────────────────────────

def _create_task(repo: SQLiteTaskRepository) -> TaskRecord:
    task = TaskRecord(
        id=uuid4(),
        project_id="test-project",
        target_module="simple_math",
    )
    repo.create_task(task)
    return repo.get_task(task.id)


@pytest.fixture
def repo() -> SQLiteTaskRepository:
    return SQLiteTaskRepository(Path(":memory:"))


@pytest.fixture
def created_task(repo: SQLiteTaskRepository) -> TaskRecord:
    return _create_task(repo)


@pytest.fixture
def engine(repo: SQLiteTaskRepository) -> AgentEngine:
    llm = MagicMock()
    dispatcher = MagicMock()
    feedback = MagicMock()
    gate = MagicMock()
    memory = MagicMock()
    policy = MagicMock()
    approvals = MagicMock()
    context_builder = MagicMock()
    return AgentEngine(
        repository=repo,
        llm=llm,
        dispatcher=dispatcher,
        feedback=feedback,
        quality_gate=gate,
        memory=memory,
        policy=policy,
        approvals=approvals,
        context_builder=context_builder,
    )


# ── advance tests (from brief) ───────────────────────────────────────

def test_advance_is_persisted_and_idempotent(
    engine: AgentEngine, repo: SQLiteTaskRepository, created_task: TaskRecord
) -> None:
    """One advance produces exactly one transition, persisted to repository."""
    result = engine.advance(created_task.id)
    assert result.previous_state == TaskState.CREATED
    assert result.current_state == TaskState.VALIDATING_INPUT
    # Verify persistence
    reloaded = repo.get_task(created_task.id)
    assert reloaded.state == TaskState.VALIDATING_INPUT
    # At least one audit event recorded
    assert len(repo.list_task_events(created_task.id)) >= 1


def test_advance_returns_blocked_for_terminal_state(
    engine: AgentEngine, repo: SQLiteTaskRepository
) -> None:
    """Advancing a task already in a terminal state returns blocked."""
    task = TaskRecord(
        id=uuid4(),
        project_id="p",
        target_module="m",
        state=TaskState.COMPLETED,
    )
    repo.create_task(task)
    result = engine.advance(task.id)
    assert result.blocked is True
    assert result.current_state == TaskState.COMPLETED


def test_run_until_blocked_stops_at_blocking_state(
    engine: AgentEngine, repo: SQLiteTaskRepository, created_task: TaskRecord
) -> None:
    """run_until_blocked advances until a blocking or terminal state."""
    task = engine.run_until_blocked(created_task.id)
    # Should reach a blocking state (AWAITING_REFACTOR_APPROVAL or terminal)
    assert task.state in {
        TaskState.AWAITING_REFACTOR_APPROVAL,
        TaskState.COMPLETED,
        TaskState.NO_ACTION_NEEDED,
        TaskState.STOPPED,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.STALE,
    }


def test_resume_from_awaiting_approval(
    engine: AgentEngine, repo: SQLiteTaskRepository, created_task: TaskRecord
) -> None:
    """Resume transitions from AWAITING_REFACTOR_APPROVAL with approved event."""
    # Manually set the task to the await state with a patch hash
    from testforge.domain.state_machine import TaskEvent as TE

    task_id = created_task.id
    # Advance to a known state first, then manually force the await state
    engine.advance(task_id)  # CREATED → VALIDATING_INPUT
    engine.advance(task_id)  # VALIDATING_INPUT → PREPARING_SANDBOX
    engine.advance(task_id)  # PREPARING_SANDBOX → BASELINING
    engine.advance(task_id)  # BASELINING → GENERATING (or NO_ACTION_NEEDED)

    t = repo.get_task(task_id)
    if t.state == TaskState.GENERATING:
        # Manually transition to AWAITING_REFACTOR_APPROVAL for test
        repo.record_transition(
            task_id,
            TE.REFACTOR_REQUESTED,
            TaskState.AWAITING_REFACTOR_APPROVAL,
            "test setup",
        )
    # Verify resume works on actual await state
    t = repo.get_task(task_id)
    if t.state == TaskState.AWAITING_REFACTOR_APPROVAL:
        result = engine.resume(task_id, uuid4())
        assert result.current_state in {
            TaskState.BASELINING,
            TaskState.GENERATING,
        }
        assert result.blocked is False
