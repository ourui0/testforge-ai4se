import pytest

from testforge.domain.state_machine import TRANSITIONS, TaskEvent, TaskState, transition


def test_evaluation_retries_when_budget_remains():
    assert transition(TaskState.EVALUATING, TaskEvent.QUALITY_MISSED) is TaskState.GENERATING


def test_refactor_request_pauses_for_approval():
    assert transition(TaskState.GENERATING, TaskEvent.REFACTOR_REQUESTED) is TaskState.AWAITING_REFACTOR_APPROVAL


def test_quality_pass_waits_for_apply_approval():
    assert transition(TaskState.EVALUATING, TaskEvent.QUALITY_PASSED) is TaskState.AWAITING_APPLY_APPROVAL


def test_transition_table_rejects_external_mutation():
    with pytest.raises(TypeError):
        TRANSITIONS[(TaskState.CREATED, TaskEvent.APPLY_SUCCEEDED)] = TaskState.COMPLETED
