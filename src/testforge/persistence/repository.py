from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from sqlalchemy import event, select, update
from sqlalchemy.engine import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from testforge.domain.errors import InputError

if TYPE_CHECKING:
    from testforge.memory import MemoryEntry

from testforge.domain.models import (
    ApprovalRequest,
    ApprovalStatus,
    AuditEvent,
    MetricSnapshot,
    TaskRecord,
    TestProposal,
)
from testforge.domain.state_machine import TaskEvent, TaskState
from testforge.persistence.schema import (
    ApprovalRow,
    AttemptRow,
    AuditEventRow,
    Base,
    MemoryEntryRow,
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

    def create_approval(self, request: ApprovalRequest) -> None:
        request = self._normalize_approval_timestamps(request)
        try:
            with self._session_factory.begin() as session:
                if session.get(ApprovalRow, str(request.id)) is not None:
                    raise InputError(f"approval {request.id} already exists")
                session.add(self._approval_row(request))
        except IntegrityError as error:
            raise InputError(f"approval {request.id} already exists") from error

    def get_approval(self, approval_id: UUID) -> ApprovalRequest:
        with self._session_factory() as session:
            row = session.get(ApprovalRow, str(approval_id))
            if row is None:
                raise InputError(f"approval {approval_id} does not exist")
            return self._approval_request(row)

    def update_approval(self, request: ApprovalRequest) -> None:
        request = self._normalize_approval_timestamps(request)
        with self._session_factory.begin() as session:
            row = session.get(ApprovalRow, str(request.id))
            if row is None:
                raise InputError(f"approval {request.id} does not exist")
            row.status = request.status.value
            row.actor = request.actor
            row.decided_at = request.decided_at
            row.expires_at = request.expires_at

    def compare_and_set_approval(
        self,
        request: ApprovalRequest,
        *,
        expected_status: ApprovalStatus,
    ) -> bool:
        request = self._normalize_approval_timestamps(request)
        with self._session_factory.begin() as session:
            result = session.execute(
                update(ApprovalRow)
                .where(
                    ApprovalRow.id == str(request.id),
                    ApprovalRow.status == expected_status.value,
                )
                .values(
                    status=request.status.value,
                    actor=request.actor,
                    decided_at=request.decided_at,
                    expires_at=request.expires_at,
                )
            )
            return result.rowcount == 1

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

    # ── memory ────────────────────────────────────────────────────

    def add_memory(self, entry: MemoryEntry) -> None:
        with self._session_factory.begin() as session:
            session.add(
                MemoryEntryRow(
                    id=str(entry.id),
                    project_id=entry.project_id,
                    kind=entry.kind,
                    tags=list(entry.tags),
                    summary=entry.summary,
                    source_task_id=(
                        str(entry.source_task_id)
                        if entry.source_task_id
                        else None
                    ),
                    created_at=entry.created_at,
                    expires_at=entry.expires_at,
                    version=entry.version,
                )
            )

    def find_memory(
        self, project_id: str, active_at: datetime
    ) -> tuple[MemoryEntry, ...]:
        with self._session_factory() as session:
            rows = (
                session.query(MemoryEntryRow)
                .filter(
                    MemoryEntryRow.project_id == project_id,
                    (
                        MemoryEntryRow.expires_at.is_(None)
                        | (MemoryEntryRow.expires_at > active_at)
                    ),
                )
                .order_by(
                    MemoryEntryRow.created_at.desc(),
                    MemoryEntryRow.version.desc(),
                    MemoryEntryRow.id.desc(),
                )
                .all()
            )
            from testforge.memory import MemoryEntry as ME

            return tuple(
                ME(
                    id=row.id,
                    project_id=row.project_id,
                    kind=row.kind,
                    tags=tuple(row.tags) if isinstance(row.tags, list) else (),
                    summary=row.summary,
                    source_task_id=row.source_task_id,
                    created_at=row.created_at,
                    expires_at=row.expires_at,
                    version=row.version,
                )
                for row in rows
            )

    def trim_memory(self, project_id: str, maximum: int) -> None:
        with self._session_factory.begin() as session:
            rows = (
                session.query(MemoryEntryRow)
                .filter(MemoryEntryRow.project_id == project_id)
                .order_by(MemoryEntryRow.created_at.desc())
                .offset(maximum)
                .all()
            )
            for row in rows:
                session.delete(row)

    def clear_project_memory(self, project_id: str) -> None:
        with self._session_factory.begin() as session:
            session.query(MemoryEntryRow).filter(
                MemoryEntryRow.project_id == project_id
            ).delete()

    # ── private ────────────────────────────────────────────────────

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
    def _approval_row(request: ApprovalRequest) -> ApprovalRow:
        return ApprovalRow(
            id=str(request.id),
            kind=request.kind,
            patch_hash=request.patch_hash,
            status=request.status.value,
            actor=request.actor,
            created_at=request.created_at,
            decided_at=request.decided_at,
            expires_at=request.expires_at,
        )

    @staticmethod
    def _approval_request(row: ApprovalRow) -> ApprovalRequest:
        def aware(value: datetime | None) -> datetime | None:
            if value is None:
                return value
            if value.tzinfo is None or value.utcoffset() is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)

        return ApprovalRequest(
            id=UUID(row.id),
            kind=row.kind,
            patch_hash=row.patch_hash,
            status=ApprovalStatus(row.status),
            actor=row.actor,
            created_at=aware(row.created_at),
            decided_at=aware(row.decided_at),
            expires_at=aware(row.expires_at),
        )

    @staticmethod
    def _normalize_approval_timestamps(
        request: ApprovalRequest,
    ) -> ApprovalRequest:
        normalized: dict[str, datetime] = {}
        for field in ("created_at", "decided_at", "expires_at"):
            value = getattr(request, field)
            if value is None:
                continue
            if value.tzinfo is None or value.utcoffset() is None:
                raise InputError(f"approval {field} must be timezone-aware")
            normalized[field] = value.astimezone(UTC)
        return request.model_copy(update=normalized)

    @staticmethod
    def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
