from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field

from testforge.config import QualityThreshold, TaskBudget
from testforge.domain.state_machine import TaskState


class MetricSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    tests_passed: int = Field(ge=0)
    tests_failed: int = Field(ge=0)
    tests_skipped: int = Field(ge=0)
    branch_coverage: float = Field(ge=0, le=100)
    mutants_total: int = Field(ge=0)
    mutants_killed: int = Field(ge=0)
    mutants_survived: int = Field(ge=0)
    mutation_status: Literal["supported", "unsupported", "timeout", "error"] = "supported"

    @computed_field
    @property
    def mutation_score(self) -> float:
        return 0.0 if self.mutants_total == 0 else 100.0 * self.mutants_killed / self.mutants_total


class TestProposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    content: str
    strategy: str


class RefactorProposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    patch: str
    reason: str
    risk: str
    alternatives: tuple[str, ...] = ()


class FeedbackPacket(BaseModel):
    model_config = ConfigDict(frozen=True)

    failure_category: str = Field(min_length=1)
    surviving_mutants: tuple[str, ...] = ()
    constraints_for_next_attempt: tuple[str, ...] = ()
    stagnated: bool = False


class BudgetUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    attempts: int = Field(default=0, ge=0)
    llm_calls: int = Field(default=0, ge=0)
    active_seconds: int = Field(default=0, ge=0)
    mutants: int = Field(default=0, ge=0)

    def exhausted(self, budget: TaskBudget) -> bool:
        return (
            self.attempts >= budget.max_attempts
            or self.llm_calls >= budget.max_llm_calls
            or self.active_seconds >= budget.max_active_seconds
            or self.mutants >= budget.max_mutants
        )


class AttemptSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    branch_coverage: float = Field(ge=0, le=100)
    mutation_score: float = Field(ge=0, le=100)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    kind: Literal["refactor", "apply_tests"]
    patch_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ApprovalStatus = ApprovalStatus.PENDING
    actor: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None
    expires_at: datetime | None = None


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    event_type: str = Field(min_length=1)
    reason: str
    occurred_at: datetime = Field(default_factory=utc_now)


class TaskRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    target_module: str = Field(min_length=1)
    state: TaskState = TaskState.CREATED
    budget: TaskBudget = TaskBudget()
    quality: QualityThreshold = QualityThreshold()
    usage: BudgetUsage = BudgetUsage()
    baseline_metrics: MetricSnapshot | None = None
    latest_metrics: MetricSnapshot | None = None
    pending_patch: str | None = None
    memory_tags: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    attempt_summaries: tuple[AttemptSummary, ...] = ()
    surviving_mutants: tuple[str, ...] = ()


class TransitionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    previous_state: TaskState
    current_state: TaskState
    blocked: bool
    reason: str
