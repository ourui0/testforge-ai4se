import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from testforge.domain.errors import InputError
from testforge.domain.models import (
    AuditEvent,
    MetricSnapshot,
    TaskRecord,
)
from testforge.domain.models import (
    TestProposal as Proposal,
)
from testforge.domain.state_machine import TaskEvent, TaskState
from testforge.persistence.repository import SQLiteTaskRepository


@pytest.fixture
def sample_task() -> TaskRecord:
    return TaskRecord(project_id="project-1", target_module="src/math.py")


def test_record_transition_updates_task_and_appends_event_atomically(
    tmp_path, sample_task
):
    repo = SQLiteTaskRepository(tmp_path / "testforge.db")
    repo.create_task(sample_task)

    repo.record_transition(
        sample_task.id,
        TaskEvent.START,
        TaskState.VALIDATING_INPUT,
        reason="started",
    )

    assert repo.get_task(sample_task.id).state is TaskState.VALIDATING_INPUT
    assert [event.reason for event in repo.list_task_events(sample_task.id)] == [
        "started"
    ]


def test_failed_event_insert_rolls_back_state(tmp_path, sample_task, monkeypatch):
    database = tmp_path / "testforge.db"
    repo = SQLiteTaskRepository(database)
    repo.create_task(sample_task)
    monkeypatch.setattr(
        repo,
        "_insert_event",
        lambda *args: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(RuntimeError, match="boom"):
        repo.record_transition(
            sample_task.id,
            TaskEvent.INPUT_VALID,
            TaskState.VALIDATING_INPUT,
            "validated",
        )

    assert repo.get_task(sample_task.id).state is TaskState.CREATED
    assert repo.list_task_events(sample_task.id) == ()


def test_repository_resumes_persisted_task_and_events(tmp_path, sample_task):
    database = tmp_path / "testforge.db"
    repo = SQLiteTaskRepository(database)
    repo.create_task(sample_task)
    repo.record_transition(
        sample_task.id,
        TaskEvent.START,
        TaskState.VALIDATING_INPUT,
        "started",
    )

    resumed_repo = SQLiteTaskRepository(database)

    assert resumed_repo.get_task(sample_task.id).state is TaskState.VALIDATING_INPUT
    assert [
        event.reason for event in resumed_repo.list_task_events(sample_task.id)
    ] == ["started"]


def test_repository_resumes_task_with_initial_metric_snapshots(tmp_path):
    database = tmp_path / "testforge.db"
    baseline = MetricSnapshot(
        tests_passed=4,
        tests_failed=1,
        tests_skipped=0,
        branch_coverage=80,
        mutants_total=10,
        mutants_killed=7,
        mutants_survived=3,
    )
    latest = MetricSnapshot(
        tests_passed=5,
        tests_failed=0,
        tests_skipped=0,
        branch_coverage=95,
        mutants_total=10,
        mutants_killed=9,
        mutants_survived=1,
    )
    task = TaskRecord(
        project_id="project-1",
        target_module="src/math.py",
        baseline_metrics=baseline,
        latest_metrics=latest,
    )

    SQLiteTaskRepository(database).create_task(task)

    resumed_task = SQLiteTaskRepository(database).get_task(task.id)
    assert resumed_task.baseline_metrics == baseline
    assert resumed_task.latest_metrics == latest


def test_in_memory_repository_is_shared_across_threads(sample_task):
    repo = SQLiteTaskRepository(Path(":memory:"))
    repo.create_task(sample_task)

    with ThreadPoolExecutor(max_workers=1) as executor:
        resumed_task = executor.submit(repo.get_task, sample_task.id).result()

    assert resumed_task == sample_task


def test_add_attempt_appends_immutable_proposal_snapshot(tmp_path, sample_task):
    database = tmp_path / "testforge.db"
    repo = SQLiteTaskRepository(database)
    repo.create_task(sample_task)
    first = Proposal(
        path="tests/test_math.py", content="assert 1 + 1 == 2", strategy="boundary"
    )
    second = Proposal(
        path="tests/test_math.py", content="assert 2 + 2 == 4", strategy="example"
    )

    repo.add_attempt(sample_task.id, first)
    repo.add_attempt(sample_task.id, second)

    with sqlite3.connect(database) as connection:
        snapshots = [
            json.loads(row[0])
            for row in connection.execute("SELECT proposal FROM attempts ORDER BY id")
        ]
    assert snapshots == [first.model_dump(mode="json"), second.model_dump(mode="json")]


@pytest.mark.parametrize(
    "kind, field", [("baseline", "baseline_metrics"), ("latest", "latest_metrics")]
)
def test_add_metric_appends_snapshot_and_updates_matching_task_field_atomically(
    tmp_path, sample_task, kind, field
):
    database = tmp_path / "testforge.db"
    repo = SQLiteTaskRepository(database)
    repo.create_task(sample_task)
    metric = MetricSnapshot(
        tests_passed=4,
        tests_failed=1,
        tests_skipped=0,
        branch_coverage=82.5,
        mutants_total=10,
        mutants_killed=8,
        mutants_survived=2,
    )

    repo.add_metric(sample_task.id, metric, kind=kind)

    assert getattr(repo.get_task(sample_task.id), field) == metric
    with sqlite3.connect(database) as connection:
        stored_kind, stored_metric = connection.execute(
            "SELECT kind, metric FROM metrics"
        ).fetchone()
    assert stored_kind == kind
    assert json.loads(stored_metric) == metric.model_dump(mode="json")


def test_add_metric_rejects_invalid_kind_without_writing(tmp_path, sample_task):
    database = tmp_path / "testforge.db"
    repo = SQLiteTaskRepository(database)
    repo.create_task(sample_task)
    metric = MetricSnapshot(
        tests_passed=1,
        tests_failed=0,
        tests_skipped=0,
        branch_coverage=100,
        mutants_total=0,
        mutants_killed=0,
        mutants_survived=0,
    )

    with pytest.raises(InputError, match="metric kind"):
        repo.add_metric(sample_task.id, metric, kind="other")  # type: ignore[arg-type]

    assert repo.get_task(sample_task.id).baseline_metrics is None
    assert repo.get_task(sample_task.id).latest_metrics is None
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM metrics").fetchone()[0] == 0


def test_task_payload_is_an_immutable_snapshot_without_current_state_or_metrics(
    tmp_path, sample_task
):
    database = tmp_path / "testforge.db"
    repo = SQLiteTaskRepository(database)
    repo.create_task(sample_task)
    with sqlite3.connect(database) as connection:
        original_payload = connection.execute("SELECT payload FROM tasks").fetchone()[0]

    repo.record_transition(
        sample_task.id,
        TaskEvent.START,
        TaskState.VALIDATING_INPUT,
        "started",
    )
    repo.add_metric(
        sample_task.id,
        MetricSnapshot(
            tests_passed=1,
            tests_failed=0,
            tests_skipped=0,
            branch_coverage=100,
            mutants_total=0,
            mutants_killed=0,
            mutants_survived=0,
        ),
        kind="latest",
    )

    with sqlite3.connect(database) as connection:
        persisted_payload = connection.execute("SELECT payload FROM tasks").fetchone()[
            0
        ]
    assert persisted_payload == original_payload
    assert "state" not in json.loads(persisted_payload)
    assert "baseline_metrics" not in json.loads(persisted_payload)
    assert "latest_metrics" not in json.loads(persisted_payload)


def test_add_audit_event_preserves_values_and_orders_ties_by_insertion(
    tmp_path, sample_task
):
    repo = SQLiteTaskRepository(tmp_path / "testforge.db")
    repo.create_task(sample_task)
    occurred_at = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    first = AuditEvent(
        task_id=sample_task.id,
        event_type="manual_review",
        reason="first",
        occurred_at=occurred_at,
    )
    second = AuditEvent(
        task_id=sample_task.id,
        event_type="manual_review",
        reason="second",
        occurred_at=occurred_at,
    )

    repo.add_audit_event(first)
    repo.add_audit_event(second)

    assert repo.list_task_events(sample_task.id) == (first, second)


def test_audit_events_are_normalized_and_ordered_by_absolute_time(
    tmp_path, sample_task
):
    repo = SQLiteTaskRepository(tmp_path / "testforge.db")
    repo.create_task(sample_task)
    later = AuditEvent(
        task_id=sample_task.id,
        event_type="later",
        reason="02:00 UTC",
        occurred_at=datetime(2026, 1, 2, 2, tzinfo=UTC),
    )
    earlier = AuditEvent(
        task_id=sample_task.id,
        event_type="earlier",
        reason="09:00 +08:00",
        occurred_at=datetime(2026, 1, 2, 9, tzinfo=timezone(timedelta(hours=8))),
    )

    repo.add_audit_event(later)
    repo.add_audit_event(earlier)

    assert repo.list_task_events(sample_task.id) == (earlier, later)


def test_add_audit_event_rejects_naive_timestamp_without_writing(tmp_path, sample_task):
    repo = SQLiteTaskRepository(tmp_path / "testforge.db")
    repo.create_task(sample_task)
    event = AuditEvent(
        task_id=sample_task.id,
        event_type="naive",
        reason="ambiguous time",
        occurred_at=datetime(2026, 1, 2, 3, 4),  # noqa: DTZ001 - intentional naive input
    )

    with pytest.raises(InputError, match="timezone-aware"):
        repo.add_audit_event(event)

    assert repo.list_task_events(sample_task.id) == ()


def test_sqlite_enforces_foreign_keys(tmp_path):
    database = tmp_path / "testforge.db"
    repo = SQLiteTaskRepository(database)

    with repo._engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1


@pytest.mark.parametrize(
    "write",
    [
        lambda repo, task_id: repo.record_transition(
            task_id, TaskEvent.START, TaskState.VALIDATING_INPUT, "started"
        ),
        lambda repo, task_id: repo.add_attempt(
            task_id,
            Proposal(path="tests/test_x.py", content="pass", strategy="example"),
        ),
        lambda repo, task_id: repo.add_metric(
            task_id,
            MetricSnapshot(
                tests_passed=0,
                tests_failed=0,
                tests_skipped=0,
                branch_coverage=0,
                mutants_total=0,
                mutants_killed=0,
                mutants_survived=0,
            ),
            kind="latest",
        ),
        lambda repo, task_id: repo.add_audit_event(
            AuditEvent(task_id=task_id, event_type="missing", reason="missing")
        ),
    ],
)
def test_writes_reject_missing_task(tmp_path, write):
    repo = SQLiteTaskRepository(tmp_path / "testforge.db")
    missing_task_id = uuid4()

    with pytest.raises(InputError, match=f"task {missing_task_id} does not exist"):
        write(repo, missing_task_id)
