from datetime import UTC
from pathlib import Path
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import create_engine
from sqlalchemy.orm import Session, sessionmaker

from testforge.domain.errors import InputError
from testforge.domain.models import (
    AuditEvent,
    MetricSnapshot,
    TaskRecord,
    TestProposal,
)
from testforge.domain.state_machine import TaskEvent, TaskState
from testforge.persistence.schema import (
    AttemptRow,
    AuditEventRow,
    Base,
    MetricRow,
    TaskRow,
)


class SQLiteTaskRepository:
    def __init__(self, path: Path) -> None:
        self._engine = create_engine(f"sqlite+pysqlite:///{path}")
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)
        Base.metadata.create_all(self._engine)

    def create_task(self, task: TaskRecord) -> None:
        with self._session_factory.begin() as session:
            session.add(
                TaskRow(
                    id=str(task.id),
                    state=task.state.value,
                    payload=task.model_dump(mode="json"),
                )
            )

    def get_task(self, task_id: UUID) -> TaskRecord:
        with self._session_factory() as session:
            row = session.get(TaskRow, str(task_id))
            if row is None:
                raise InputError(f"task {task_id} does not exist")
            return TaskRecord.model_validate({**row.payload, "state": row.state})

    def record_transition(
        self,
        task_id: UUID,
        event: TaskEvent,
        next_state: TaskState,
        reason: str,
    ) -> None:
        audit_event = AuditEvent(
            task_id=task_id,
            event_type=event.value,
            reason=reason,
        )
        with self._session_factory.begin() as session:
            row = session.get(TaskRow, str(task_id))
            if row is None:
                raise InputError(f"task {task_id} does not exist")
            row.state = next_state.value
            self._insert_event(session, self._event_row(audit_event))

    def add_attempt(self, task_id: UUID, proposal: TestProposal) -> None:
        with self._session_factory.begin() as session:
            self._require_task(session, task_id)
            session.add(
                AttemptRow(
                    task_id=str(task_id),
                    proposal=proposal.model_dump(mode="json"),
                )
            )

    def add_metric(
        self,
        task_id: UUID,
        metric: MetricSnapshot,
        *,
        kind: Literal["baseline", "latest"],
    ) -> None:
        if kind not in {"baseline", "latest"}:
            raise InputError(f"metric kind {kind!r} is invalid")

        with self._session_factory.begin() as session:
            row = self._require_task(session, task_id)
            metric_payload = metric.model_dump(mode="json")
            session.add(
                MetricRow(
                    task_id=str(task_id),
                    kind=kind,
                    metric=metric_payload,
                )
            )
            task_payload = dict(row.payload)
            task_payload[f"{kind}_metrics"] = metric_payload
            row.payload = task_payload

    def add_audit_event(self, event: AuditEvent) -> None:
        with self._session_factory.begin() as session:
            self._require_task(session, event.task_id)
            self._insert_event(session, self._event_row(event))

    def list_task_events(self, task_id: UUID) -> tuple[AuditEvent, ...]:
        with self._session_factory() as session:
            statement = (
                select(AuditEventRow)
                .where(AuditEventRow.task_id == str(task_id))
                .order_by(AuditEventRow.occurred_at, AuditEventRow.sequence)
            )
            return tuple(
                AuditEvent(
                    id=UUID(row.id),
                    task_id=UUID(row.task_id),
                    event_type=row.event_type,
                    reason=row.reason,
                    occurred_at=(
                        row.occurred_at.replace(tzinfo=UTC)
                        if row.occurred_at.tzinfo is None
                        else row.occurred_at
                    ),
                )
                for row in session.scalars(statement)
            )

    def _insert_event(self, session: Session, row: AuditEventRow) -> None:
        session.add(row)

    @staticmethod
    def _require_task(session: Session, task_id: UUID) -> TaskRow:
        row = session.get(TaskRow, str(task_id))
        if row is None:
            raise InputError(f"task {task_id} does not exist")
        return row

    @staticmethod
    def _event_row(event: AuditEvent) -> AuditEventRow:
        return AuditEventRow(
            id=str(event.id),
            task_id=str(event.task_id),
            event_type=event.event_type,
            reason=event.reason,
            occurred_at=event.occurred_at,
        )
