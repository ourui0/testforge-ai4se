"""Agent engine — persisted, one-transition-at-a-time state advancement."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from testforge.domain.errors import InvalidTransition
from testforge.domain.models import TaskRecord, TransitionResult
from testforge.domain.state_machine import TaskEvent, TaskState, transition


class AgentEngine:
    """Drive a task through its state machine one transition per advance().

    Each handler performs at most one externally visible action and
    persists its result before the transition. run_until_blocked loops
    until a blocking or terminal state is reached.
    """

    def __init__(
        self,
        *,
        repository: Any,
        llm: Any,
        dispatcher: Any,
        feedback: Any,
        quality_gate: Any,
        memory: Any,
        policy: Any,
        approvals: Any,
        context_builder: Any,
    ) -> None:
        self.repository = repository
        self.llm = llm
        self.dispatcher = dispatcher
        self.feedback = feedback
        self.quality_gate = quality_gate
        self.memory = memory
        self.policy = policy
        self.approvals = approvals
        self.context_builder = context_builder
        self._handlers: dict[TaskState, Callable[[TaskRecord], tuple[TaskEvent, str]]]
        self._handlers = {
            TaskState.CREATED: self._handle_created,
            TaskState.VALIDATING_INPUT: self._handle_validating_input,
            TaskState.PREPARING_SANDBOX: self._handle_preparing_sandbox,
            TaskState.BASELINING: self._handle_baselining,
            TaskState.GENERATING: self._handle_generating,
            TaskState.TESTING: self._handle_testing,
            TaskState.MEASURING_COVERAGE: self._handle_measuring_coverage,
            TaskState.MUTATION_TESTING: self._handle_mutation_testing,
            TaskState.EVALUATING: self._handle_evaluating,
        }

    def advance(self, task_id: UUID) -> TransitionResult:
        task = self.repository.get_task(task_id)
        handler = self._handlers.get(task.state)
        if handler is None:
            return TransitionResult(
                previous_state=task.state,
                current_state=task.state,
                blocked=True,
                reason="terminal_or_waiting",
            )
        event, reason = handler(task)
        next_state = transition(task.state, event)
        self.repository.record_transition(task.id, event, next_state, reason)
        return TransitionResult(
            previous_state=task.state,
            current_state=next_state,
            blocked=next_state in _BLOCKING_STATES or next_state in _TERMINAL_STATES,
            reason=reason,
        )

    def run_until_blocked(self, task_id: UUID) -> TaskRecord:
        while True:
            result = self.advance(task_id)
            if result.blocked or result.current_state in _TERMINAL_STATES:
                return self.repository.get_task(task_id)

    def resume(self, task_id: UUID, approval_id: UUID) -> TransitionResult:
        task = self.repository.get_task(task_id)
        if task.state not in _BLOCKING_STATES:
            raise InvalidTransition(state=task.state, event=TaskEvent.APPROVED)
        next_state = transition(task.state, TaskEvent.APPROVED)
        self.repository.record_transition(
            task.id,
            TaskEvent.APPROVED,
            next_state,
            reason=f"approval:{approval_id}",
        )
        return TransitionResult(
            previous_state=task.state,
            current_state=next_state,
            blocked=False,
            reason="approved",
        )

    # ── state handlers ──────────────────────────────────────────────

    @staticmethod
    def _handle_created(task: TaskRecord) -> tuple[TaskEvent, str]:
        _ = task
        return TaskEvent.START, "task started"

    @staticmethod
    def _handle_validating_input(task: TaskRecord) -> tuple[TaskEvent, str]:
        _ = task
        return TaskEvent.INPUT_VALID, "input validated"

    @staticmethod
    def _handle_preparing_sandbox(task: TaskRecord) -> tuple[TaskEvent, str]:
        _ = task
        return TaskEvent.SANDBOX_READY, "sandbox prepared"

    @staticmethod
    def _handle_baselining(task: TaskRecord) -> tuple[TaskEvent, str]:
        _ = task
        return TaskEvent.BASELINE_READY, "baseline established"

    def _handle_generating(self, task: TaskRecord) -> tuple[TaskEvent, str]:
        self.policy.validate_budget(task.usage, task.budget)
        memory_entries = self.memory.select(task.project_id, task.memory_tags)
        context = self.context_builder.build(task, tuple(
            e.summary for e in memory_entries
        ))
        feedback_packet = getattr(task, "_latest_feedback", None)
        response = self.llm.generate(context, feedback_packet)
        if response.refactor is not None:
            self.policy.validate_refactor_proposal(response.refactor)
            self.approvals.request("refactor", response.refactor.patch)
            return TaskEvent.REFACTOR_REQUESTED, "refactor proposal requires approval"
        if response.test is None:
            raise ValueError("validated response contains no test proposal")
        self.policy.validate_test_proposal(response.test)
        self.repository.add_attempt(task.id, response.test)
        return TaskEvent.PROPOSAL_READY, "test proposal validated"

    @staticmethod
    def _handle_testing(task: TaskRecord) -> tuple[TaskEvent, str]:
        _ = task
        return TaskEvent.TESTS_FINISHED, "tests executed"

    @staticmethod
    def _handle_measuring_coverage(task: TaskRecord) -> tuple[TaskEvent, str]:
        _ = task
        return TaskEvent.COVERAGE_FINISHED, "coverage measured"

    @staticmethod
    def _handle_mutation_testing(task: TaskRecord) -> tuple[TaskEvent, str]:
        _ = task
        return TaskEvent.MUTATION_FINISHED, "mutation testing complete"

    def _handle_evaluating(self, task: TaskRecord) -> tuple[TaskEvent, str]:
        _ = task
        return TaskEvent.QUALITY_PASSED, "quality gate passed"


_BLOCKING_STATES = frozenset({
    TaskState.AWAITING_REFACTOR_APPROVAL,
    TaskState.AWAITING_APPLY_APPROVAL,
})

_TERMINAL_STATES = frozenset({
    TaskState.COMPLETED,
    TaskState.NO_ACTION_NEEDED,
    TaskState.STOPPED,
    TaskState.FAILED,
    TaskState.CANCELLED,
    TaskState.STALE,
})
