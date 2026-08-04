import pytest
from pydantic import ValidationError

from testforge.config import TaskBudget
from testforge.domain.models import (
    ApprovalRequest,
    AttemptSummary,
    BudgetUsage,
    FeedbackPacket,
    MetricSnapshot,
    RefactorProposal,
    TaskRecord,
)
from testforge.domain.models import (
    TestProposal as Proposal,
)
from testforge.domain.state_machine import TaskState


def test_test_proposal_is_a_single_test_file_replacement():
    proposal = Proposal(
        path="tests/test_math.py",
        content="def test_add():\n    assert 1 + 1 == 2\n",
        strategy="boundary assertion",
    )

    assert proposal.path.startswith("tests/")


def test_metric_snapshot_computes_mutation_score():
    metrics = MetricSnapshot(
        tests_passed=4,
        tests_failed=0,
        tests_skipped=0,
        branch_coverage=75.0,
        mutants_total=4,
        mutants_killed=3,
        mutants_survived=1,
    )

    assert metrics.mutation_score == 75.0


def test_shared_domain_contracts_have_safe_immutable_defaults():
    refactor = RefactorProposal(path="src/math.py", patch="@@ -1 +1 @@", reason="isolate clock", risk="low")
    feedback = FeedbackPacket(
        failure_category="surviving_mutant",
        surviving_mutants=("src/math.py:1",),
        constraints_for_next_attempt=("add a boundary assertion",),
    )
    usage = BudgetUsage(attempts=5, llm_calls=1, active_seconds=2, mutants=3)
    attempt = AttemptSummary(branch_coverage=80.0, mutation_score=75.0)
    task = TaskRecord(project_id="project-1", target_module="src/math.py", attempt_summaries=(attempt,))

    assert refactor.alternatives == ()
    assert feedback.stagnated is False
    assert usage.exhausted(TaskBudget()) is True
    assert task.state is TaskState.CREATED
    assert task.pending_patch is None
    with pytest.raises(ValidationError):
        task.state = TaskState.FAILED


def test_approval_request_requires_sha256_patch_hash():
    with pytest.raises(ValidationError):
        ApprovalRequest(kind="apply_tests", patch_hash="not-a-sha256")
