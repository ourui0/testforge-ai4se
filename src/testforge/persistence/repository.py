from datetime import UTC
from pathlib import Path
from typing import Literal
from uuid import UUID

from sqlalchemy import event, select
from sqlalchemy.engine import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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
        engine_options: dict[str, object] = {}
        if str(path) == ":memory:":
            engine_options = {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            }
        self._engine = create_engine(
            f"sqlite+pysqlite:///{path}",
            **engine_options,
        )
        event.listen(self._engine, "connect", self._enable_foreign_keys)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)
        Base.metadata.create_all(self._engine)

    def create_task(self, task: TaskRecord) -> None:
        with self._session_factory.begin() as session:
            session.add(
                TaskRow(
                    id=str(task.id),
                    state=task.state.value,
                    payload=task.model_dump(
                        mode="json",
                        exclude={"state", "baseline_metrics", "latest_metrics"},
                    ),
                )
            )
            session.flush()
            for kind, metric in (
                ("baseline", task.baseline_metrics),
                ("latest", task.latest_metrics),
            ):
                if metric is not None:
                    session.add(
                        MetricRow(
                            task_id=str(task.id),
                            kind=kind,
                            metric=metric.model_dump(mode="json"),
                        )
                    )

    def get_task(self, task_id: UUID) -> TaskRecord:
        with self._session_factory() as session:
            row = session.get(TaskRow, str(task_id))
            if row is None:
                raise InputError(f"task {task_id} does not exist")
            task_data = {**row.payload, "state": row.state}
            for kind in ("baseline", "latest"):
                metric = session.scalar(
                    select(MetricRow.metric)
                    .where(
                        MetricRow.task_id == str(task_id),
                        MetricRow.kind == kind,
                    )
                    .order_by(MetricRow.id.desc())
                    .limit(1)
                )
                task_data[f"{kind}_metrics"] = metric
            return TaskRecord.model_validate(task_data)

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
            self._require_task(session, task_id)
            metric_payload = metric.model_dump(mode="json")
            session.add(
                MetricRow(
                    task_id=str(task_id),
                    kind=kind,
                    metric=metric_payload,
                )
            )

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
        if event.occurred_at.tzinfo is None or event.occurred_at.utcoffset() is None:
            raise InputError("audit event timestamp must be timezone-aware")
        return AuditEventRow(
            id=str(event.id),
            task_id=str(event.task_id),
            event_type=event.event_type,
            reason=event.reason,
            occurred_at=event.occurred_at.astimezone(UTC),
        )

    @staticmethod
    def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
