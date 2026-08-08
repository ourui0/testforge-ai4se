from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from testforge.domain.errors import InvalidTransition


class TaskState(StrEnum):
    CREATED = "created"
    VALIDATING_INPUT = "validating_input"
    PREPARING_SANDBOX = "preparing_sandbox"
    BASELINING = "baselining"
    GENERATING = "generating"
    TESTING = "testing"
    MEASURING_COVERAGE = "measuring_coverage"
    MUTATION_TESTING = "mutation_testing"
    EVALUATING = "evaluating"
    AWAITING_REFACTOR_APPROVAL = "awaiting_refactor_approval"
    AWAITING_APPLY_APPROVAL = "awaiting_apply_approval"
    APPLYING_PATCH = "applying_patch"
    COMPLETED = "completed"
    NO_ACTION_NEEDED = "no_action_needed"
    STOPPED = "stopped"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"


class TaskEvent(StrEnum):
    START = "start"
    INPUT_VALID = "input_valid"
    SANDBOX_READY = "sandbox_ready"
    BASELINE_READY = "baseline_ready"
    PROPOSAL_READY = "proposal_ready"
    TESTS_FINISHED = "tests_finished"
    COVERAGE_FINISHED = "coverage_finished"
    MUTATION_FINISHED = "mutation_finished"
    QUALITY_MISSED = "quality_missed"
    QUALITY_PASSED = "quality_passed"
    REFACTOR_REQUESTED = "refactor_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    NO_GAP = "no_gap"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANCEL = "cancel"
    ERROR = "error"
    WORKSPACE_CHANGED = "workspace_changed"
    APPLY_SUCCEEDED = "apply_succeeded"


def transition(state: TaskState, event: TaskEvent) -> TaskState:
    key = (state, event)
    if key not in TRANSITIONS:
        raise InvalidTransition(state=state, event=event)
    return TRANSITIONS[key]


_TRANSITIONS: dict[tuple[TaskState, TaskEvent], TaskState] = {
    (TaskState.CREATED, TaskEvent.START): TaskState.VALIDATING_INPUT,
    (TaskState.VALIDATING_INPUT, TaskEvent.INPUT_VALID): TaskState.PREPARING_SANDBOX,
    (TaskState.PREPARING_SANDBOX, TaskEvent.SANDBOX_READY): TaskState.BASELINING,
    (TaskState.BASELINING, TaskEvent.BASELINE_READY): TaskState.GENERATING,
    (TaskState.BASELINING, TaskEvent.NO_GAP): TaskState.NO_ACTION_NEEDED,
    (TaskState.GENERATING, TaskEvent.PROPOSAL_READY): TaskState.TESTING,
    (TaskState.GENERATING, TaskEvent.REFACTOR_REQUESTED): TaskState.AWAITING_REFACTOR_APPROVAL,
    (TaskState.TESTING, TaskEvent.TESTS_FINISHED): TaskState.MEASURING_COVERAGE,
    (TaskState.MEASURING_COVERAGE, TaskEvent.COVERAGE_FINISHED): TaskState.MUTATION_TESTING,
    (TaskState.MUTATION_TESTING, TaskEvent.MUTATION_FINISHED): TaskState.EVALUATING,
    (TaskState.EVALUATING, TaskEvent.QUALITY_MISSED): TaskState.GENERATING,
    (TaskState.EVALUATING, TaskEvent.QUALITY_PASSED): TaskState.AWAITING_APPLY_APPROVAL,
    (TaskState.AWAITING_REFACTOR_APPROVAL, TaskEvent.APPROVED): TaskState.BASELINING,
    (TaskState.AWAITING_REFACTOR_APPROVAL, TaskEvent.REJECTED): TaskState.GENERATING,
    (TaskState.AWAITING_APPLY_APPROVAL, TaskEvent.APPROVED): TaskState.APPLYING_PATCH,
    (TaskState.AWAITING_APPLY_APPROVAL, TaskEvent.REJECTED): TaskState.STOPPED,
    (TaskState.APPLYING_PATCH, TaskEvent.APPLY_SUCCEEDED): TaskState.COMPLETED,
}

for active_state in set(TaskState) - {
    TaskState.COMPLETED,
    TaskState.NO_ACTION_NEEDED,
    TaskState.STOPPED,
    TaskState.FAILED,
    TaskState.CANCELLED,
}:
    _TRANSITIONS[(active_state, TaskEvent.CANCEL)] = TaskState.CANCELLED
    _TRANSITIONS[(active_state, TaskEvent.ERROR)] = TaskState.FAILED
    _TRANSITIONS[(active_state, TaskEvent.WORKSPACE_CHANGED)] = TaskState.STALE

for budgeted_state in {
    TaskState.GENERATING,
    TaskState.TESTING,
    TaskState.MEASURING_COVERAGE,
    TaskState.MUTATION_TESTING,
    TaskState.EVALUATING,
}:
    _TRANSITIONS[(budgeted_state, TaskEvent.BUDGET_EXHAUSTED)] = TaskState.STOPPED


TRANSITIONS: Mapping[tuple[TaskState, TaskEvent], TaskState] = MappingProxyType(_TRANSITIONS)
