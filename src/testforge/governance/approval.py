import hashlib
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID

from testforge.domain.errors import InputError, PolicyViolation
from testforge.domain.models import ApprovalRequest, ApprovalStatus
from testforge.persistence.repository import SQLiteTaskRepository


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ApprovalService:
    def __init__(
        self,
        repository: SQLiteTaskRepository,
        clock: Clock | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or SystemClock()

    def request(
        self,
        kind: Literal["refactor", "apply_tests"],
        patch: str,
        expires_at: datetime | None = None,
    ) -> ApprovalRequest:
        now = self._utc_now()
        if expires_at is not None:
            if expires_at.tzinfo is None or expires_at.utcoffset() is None:
                raise InputError("approval expiry must be timezone-aware")
            expires_at = expires_at.astimezone(UTC)
            if expires_at <= now:
                raise InputError("approval expiry must be later than creation time")
        request = ApprovalRequest(
            kind=kind,
            patch_hash=sha256_text(patch),
            status=ApprovalStatus.PENDING,
            created_at=now,
            expires_at=expires_at,
        )
        self.repository.create_approval(request)
        return request

    def decide(
        self,
        approval_id: UUID,
        approved: bool,
        patch_hash: str,
        actor: str,
    ) -> ApprovalRequest:
        now = self._utc_now()
        request = self.repository.get_approval(approval_id)
        self._reject_if_expired(request, now)
        desired_status = (
            ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        )
        if request.status is not ApprovalStatus.PENDING:
            if (
                request.status is desired_status
                and request.patch_hash == patch_hash
                and request.actor == actor
            ):
                return request
            raise PolicyViolation("approval request was already decided")
        if request.patch_hash != patch_hash:
            raise PolicyViolation("decision patch hash does not match request")
        decided = request.model_copy(
            update={
                "status": desired_status,
                "actor": actor,
                "decided_at": now,
            }
        )
        self.repository.update_approval(decided)
        return decided

    def require_approved(self, approval_id: UUID, patch: str) -> ApprovalRequest:
        now = self._utc_now()
        request = self.repository.get_approval(approval_id)
        self._reject_if_expired(request, now)
        if (
            request.status is not ApprovalStatus.APPROVED
            or request.patch_hash != sha256_text(patch)
        ):
            raise PolicyViolation("approval does not match patch hash")
        return request

    def _utc_now(self) -> datetime:
        current = self.clock.now()
        if current.tzinfo is None or current.utcoffset() is None:
            raise InputError("clock must return a timezone-aware datetime")
        return current.astimezone(UTC)

    def _reject_if_expired(self, request: ApprovalRequest, now: datetime) -> None:
        if request.expires_at is None or request.expires_at > now:
            return
        if request.status is not ApprovalStatus.EXPIRED:
            request = request.model_copy(update={"status": ApprovalStatus.EXPIRED})
            self.repository.update_approval(request)
        raise PolicyViolation("approval request has expired")
