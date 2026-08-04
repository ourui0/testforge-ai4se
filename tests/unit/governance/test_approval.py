import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from testforge.domain.errors import InputError, PolicyViolation
from testforge.domain.models import ApprovalStatus
from testforge.governance.approval import ApprovalService, SystemClock, sha256_text
from testforge.persistence.repository import SQLiteTaskRepository


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


class NaiveClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 5, 12, 0)  # noqa: DTZ001 - intentional


@pytest.fixture
def approval_service(tmp_path):
    repository = SQLiteTaskRepository(tmp_path / "testforge.db")
    return ApprovalService(repository, FixedClock())


def test_approval_is_valid_only_for_exact_patch(approval_service):
    request = approval_service.request(kind="apply_tests", patch="original")
    approval_service.decide(
        request.id,
        approved=True,
        patch_hash=request.patch_hash,
        actor="owner",
    )
    with pytest.raises(PolicyViolation, match="patch hash"):
        approval_service.require_approved(request.id, patch="changed")


def test_approval_returns_stored_request_for_exact_patch(approval_service):
    request = approval_service.request(kind="apply_tests", patch="original")
    decided = approval_service.decide(
        request.id,
        approved=True,
        patch_hash=request.patch_hash,
        actor="owner",
    )

    assert approval_service.require_approved(request.id, patch="original") == decided


def test_system_clock_returns_utc_aware_time():
    current = SystemClock().now()

    assert current.tzinfo is UTC
    assert current.utcoffset() == timedelta(0)


def test_request_and_decision_use_injected_timestamps_normalized_to_utc(tmp_path):
    local_zone = timezone(timedelta(hours=8))
    clock = MutableClock(datetime(2026, 8, 5, 20, 0, tzinfo=local_zone))
    service = ApprovalService(
        SQLiteTaskRepository(tmp_path / "testforge.db"),
        clock,
    )

    request = service.request(kind="refactor", patch="patch")
    clock.current = datetime(2026, 8, 5, 20, 5, tzinfo=local_zone)
    decided = service.decide(
        request.id,
        approved=False,
        patch_hash=request.patch_hash,
        actor="owner",
    )

    assert request.created_at == datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    assert decided.decided_at == datetime(2026, 8, 5, 12, 5, tzinfo=UTC)


def test_request_rejects_naive_clock_without_persisting(tmp_path):
    database = tmp_path / "testforge.db"
    repository = SQLiteTaskRepository(database)
    service = ApprovalService(repository, NaiveClock())

    with pytest.raises(InputError, match="timezone-aware"):
        service.request(kind="apply_tests", patch="patch")

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0


@pytest.mark.parametrize("operation", ["decide", "require"])
def test_existing_approval_operations_reject_naive_clock(tmp_path, operation):
    repository = SQLiteTaskRepository(tmp_path / "testforge.db")
    aware_service = ApprovalService(repository, FixedClock())
    request = aware_service.request(kind="apply_tests", patch="patch")
    service = ApprovalService(repository, NaiveClock())

    with pytest.raises(InputError, match="timezone-aware"):
        if operation == "decide":
            service.decide(
                request.id,
                approved=True,
                patch_hash=request.patch_hash,
                actor="owner",
            )
        else:
            service.require_approved(request.id, patch="patch")

    assert repository.get_approval(request.id).status is ApprovalStatus.PENDING


@pytest.mark.parametrize(
    "expires_at",
    [
        datetime(2026, 8, 5, 12, 0),  # noqa: DTZ001 - intentional
        datetime(2026, 8, 5, 12, 0, tzinfo=UTC),
        datetime(2026, 8, 5, 11, 59, tzinfo=UTC),
    ],
)
def test_request_rejects_invalid_expiry(tmp_path, expires_at):
    service = ApprovalService(
        SQLiteTaskRepository(tmp_path / "testforge.db"),
        FixedClock(),
    )

    with pytest.raises(InputError, match="expiry"):
        service.request(
            kind="apply_tests",
            patch="patch",
            expires_at=expires_at,
        )


def test_expired_pending_request_is_persisted_and_cannot_be_decided(tmp_path):
    database = tmp_path / "testforge.db"
    repository = SQLiteTaskRepository(database)
    clock = MutableClock(datetime(2026, 8, 5, 12, 0, tzinfo=UTC))
    service = ApprovalService(repository, clock)
    request = service.request(
        kind="apply_tests",
        patch="patch",
        expires_at=clock.current + timedelta(minutes=5),
    )
    clock.current = request.expires_at

    with pytest.raises(PolicyViolation, match="expired"):
        service.decide(
            request.id,
            approved=True,
            patch_hash=request.patch_hash,
            actor="owner",
        )

    assert (
        SQLiteTaskRepository(database).get_approval(request.id).status
        is ApprovalStatus.EXPIRED
    )


def test_expired_approval_is_persisted_and_cannot_be_required(tmp_path):
    database = tmp_path / "testforge.db"
    repository = SQLiteTaskRepository(database)
    clock = MutableClock(datetime(2026, 8, 5, 12, 0, tzinfo=UTC))
    service = ApprovalService(repository, clock)
    request = service.request(
        kind="apply_tests",
        patch="patch",
        expires_at=clock.current + timedelta(minutes=5),
    )
    service.decide(
        request.id,
        approved=True,
        patch_hash=request.patch_hash,
        actor="owner",
    )
    clock.current = request.expires_at

    with pytest.raises(PolicyViolation, match="expired"):
        service.require_approved(request.id, patch="patch")

    assert (
        SQLiteTaskRepository(database).get_approval(request.id).status
        is ApprovalStatus.EXPIRED
    )


def test_identical_repeated_decision_is_idempotent(tmp_path):
    repository = SQLiteTaskRepository(tmp_path / "testforge.db")
    clock = MutableClock(datetime(2026, 8, 5, 12, 0, tzinfo=UTC))
    service = ApprovalService(repository, clock)
    request = service.request(kind="apply_tests", patch="patch")
    first = service.decide(
        request.id,
        approved=True,
        patch_hash=request.patch_hash,
        actor="owner",
    )
    clock.current += timedelta(hours=1)

    repeated = service.decide(
        request.id,
        approved=True,
        patch_hash=request.patch_hash,
        actor="owner",
    )

    assert repeated == first
    assert repeated.decided_at == datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("approved", "patch_hash", "actor"),
    [
        (False, sha256_text("patch"), "owner"),
        (True, sha256_text("different"), "owner"),
        (True, sha256_text("patch"), "other"),
    ],
)
def test_conflicting_repeated_decision_is_rejected(
    tmp_path, approved, patch_hash, actor
):
    repository = SQLiteTaskRepository(tmp_path / "testforge.db")
    service = ApprovalService(repository, FixedClock())
    request = service.request(kind="apply_tests", patch="patch")
    first = service.decide(
        request.id,
        approved=True,
        patch_hash=request.patch_hash,
        actor="owner",
    )

    with pytest.raises(PolicyViolation, match="already decided"):
        service.decide(
            request.id,
            approved=approved,
            patch_hash=patch_hash,
            actor=actor,
        )

    assert repository.get_approval(request.id) == first


def test_duplicate_and_missing_approval_ids_raise_input_error(tmp_path):
    repository = SQLiteTaskRepository(tmp_path / "testforge.db")
    service = ApprovalService(repository, FixedClock())
    request = service.request(kind="apply_tests", patch="patch")

    with pytest.raises(InputError, match="already exists"):
        repository.create_approval(request)

    missing = uuid4()
    with pytest.raises(InputError, match=f"approval {missing} does not exist"):
        repository.get_approval(missing)
    with pytest.raises(InputError, match=f"approval {missing} does not exist"):
        repository.update_approval(request.model_copy(update={"id": missing}))


def test_repository_update_preserves_immutable_approval_fields(tmp_path):
    repository = SQLiteTaskRepository(tmp_path / "testforge.db")
    service = ApprovalService(repository, FixedClock())
    request = service.request(kind="apply_tests", patch="patch")
    changed = request.model_copy(
        update={
            "kind": "refactor",
            "patch_hash": sha256_text("changed"),
            "created_at": request.created_at + timedelta(days=1),
            "status": ApprovalStatus.APPROVED,
            "actor": "owner",
            "decided_at": request.created_at + timedelta(minutes=1),
        }
    )

    repository.update_approval(changed)

    stored = repository.get_approval(request.id)
    assert stored.id == request.id
    assert stored.kind == request.kind
    assert stored.patch_hash == request.patch_hash
    assert stored.created_at == request.created_at
    assert stored.status is ApprovalStatus.APPROVED
    assert stored.actor == "owner"


def test_repository_resumes_persisted_approval(tmp_path):
    database = tmp_path / "testforge.db"
    service = ApprovalService(SQLiteTaskRepository(database), FixedClock())
    request = service.request(
        kind="apply_tests",
        patch="patch",
        expires_at=datetime(2026, 8, 6, 12, 0, tzinfo=UTC),
    )
    decided = service.decide(
        request.id,
        approved=True,
        patch_hash=request.patch_hash,
        actor="owner",
    )

    assert SQLiteTaskRepository(database).get_approval(request.id) == decided
