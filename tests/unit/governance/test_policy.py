from pathlib import Path

import pytest

from testforge.config import ProjectConfig, TaskBudget
from testforge.domain.errors import PolicyViolation
from testforge.domain.models import BudgetUsage, RefactorProposal
from testforge.domain.models import TestProposal as CandidateTestProposal
from testforge.governance.policy import GovernancePolicy


@pytest.fixture
def policy(tmp_path: Path) -> GovernancePolicy:
    config = ProjectConfig(
        repository_root=tmp_path,
        target_module="src/calculator.py",
        tests_root=Path("tests"),
    )
    return GovernancePolicy(config)


def test_rejects_parent_directory_escape(policy: GovernancePolicy) -> None:
    with pytest.raises(PolicyViolation, match="outside repository"):
        policy.validate_read("../secrets.txt")


def test_rejects_source_write_without_refactor_approval(
    policy: GovernancePolicy,
) -> None:
    proposal = CandidateTestProposal(
        path="src/calculator.py", content="pass\n", strategy="make test pass"
    )
    with pytest.raises(PolicyViolation, match="test directory"):
        policy.validate_test_proposal(proposal)


def test_rejects_absolute_path_inside_repository(policy: GovernancePolicy) -> None:
    absolute_path = policy.repository_root / "tests" / "test_calculator.py"

    with pytest.raises(PolicyViolation, match="repository-relative"):
        policy.validate_read(str(absolute_path))


def test_rejects_root_anchored_path(policy: GovernancePolicy) -> None:
    with pytest.raises(PolicyViolation, match="repository-relative"):
        policy.validate_read("/tests/test_calculator.py")


def test_returns_canonical_repository_path(policy: GovernancePolicy) -> None:
    assert policy.validate_read("tests/../src/calculator.py") == (
        policy.repository_root / "src" / "calculator.py"
    )


@pytest.mark.parametrize("field", ["tests_root", "target_module"])
def test_rejects_absolute_configured_paths(tmp_path: Path, field: str) -> None:
    values: dict[str, object] = {
        "repository_root": tmp_path,
        "target_module": "src/calculator.py",
        "tests_root": Path("tests"),
    }
    values[field] = (
        tmp_path / "tests"
        if field == "tests_root"
        else str(tmp_path / "src" / "calculator.py")
    )

    with pytest.raises(PolicyViolation, match="repository-relative"):
        GovernancePolicy(ProjectConfig(**values))  # type: ignore[arg-type]


def test_rejects_symlink_escape(policy: GovernancePolicy, tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("private", encoding="utf-8")
    link = policy.repository_root / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("test environment does not permit symlink creation")

    with pytest.raises(PolicyViolation, match="outside repository"):
        policy.validate_read("linked.txt")


@pytest.fixture
def existing_test(policy: GovernancePolicy) -> Path:
    test_path = policy.repository_root / "tests" / "test_existing.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("def test_existing():\n    pass\n", encoding="utf-8")
    return test_path


def test_rejects_empty_replacement_of_existing_test(
    policy: GovernancePolicy, existing_test: Path
) -> None:
    proposal = CandidateTestProposal(
        path=existing_test.relative_to(policy.repository_root).as_posix(),
        content="",
        strategy="delete",
    )

    with pytest.raises(PolicyViolation, match="deletion"):
        policy.validate_test_proposal(proposal)


def test_rejects_empty_new_test(policy: GovernancePolicy) -> None:
    proposal = CandidateTestProposal(
        path="tests/test_new.py", content="", strategy="empty"
    )

    with pytest.raises(PolicyViolation, match="non-empty"):
        policy.validate_test_proposal(proposal)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("\u00e9\u00e9\u00e9", "byte limit"),
        ("a\nb\nc", "line limit"),
    ],
)
def test_rejects_test_content_over_patch_limits(
    tmp_path: Path, content: str, message: str
) -> None:
    policy = GovernancePolicy(
        ProjectConfig(repository_root=tmp_path, target_module="src/calculator.py"),
        max_patch_bytes=5,
        max_patch_lines=2,
    )
    proposal = CandidateTestProposal(
        path="tests/test_new.py", content=content, strategy="boundary"
    )

    with pytest.raises(PolicyViolation, match=message):
        policy.validate_test_proposal(proposal)


def test_accepts_test_content_at_patch_limits(tmp_path: Path) -> None:
    policy = GovernancePolicy(
        ProjectConfig(repository_root=tmp_path, target_module="src/calculator.py"),
        max_patch_bytes=5,
        max_patch_lines=2,
    )
    proposal = CandidateTestProposal(
        path="tests/test_new.py", content="\u00e9\nab", strategy="boundary"
    )

    assert policy.validate_test_proposal(proposal) == (
        tmp_path / "tests" / "test_new.py"
    )


def test_accepts_refactor_for_exact_target(policy: GovernancePolicy) -> None:
    proposal = RefactorProposal(
        path="src/./calculator.py",
        patch="@@ -1 +1 @@\n-pass\n+return 1",
        reason="improve testability",
        risk="low",
    )

    assert policy.validate_refactor_proposal(proposal) == (
        policy.repository_root / "src" / "calculator.py"
    )


def test_rejects_refactor_outside_exact_target(policy: GovernancePolicy) -> None:
    proposal = RefactorProposal(
        path="src/other.py",
        patch="@@ -1 +1 @@\n-pass\n+return 1",
        reason="unrelated",
        risk="high",
    )

    with pytest.raises(PolicyViolation, match="target module"):
        policy.validate_refactor_proposal(proposal)


def test_rejects_empty_refactor_patch(policy: GovernancePolicy) -> None:
    proposal = RefactorProposal(
        path="src/calculator.py",
        patch="",
        reason="delete",
        risk="high",
    )

    with pytest.raises(PolicyViolation, match="non-empty"):
        policy.validate_refactor_proposal(proposal)


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ("\u00e9\u00e9\u00e9", "byte limit"),
        ("a\nb\nc", "line limit"),
    ],
)
def test_rejects_refactor_patch_over_limits(
    tmp_path: Path, patch: str, message: str
) -> None:
    policy = GovernancePolicy(
        ProjectConfig(repository_root=tmp_path, target_module="src/calculator.py"),
        max_patch_bytes=5,
        max_patch_lines=2,
    )
    proposal = RefactorProposal(
        path="src/calculator.py", patch=patch, reason="boundary", risk="low"
    )

    with pytest.raises(PolicyViolation, match=message):
        policy.validate_refactor_proposal(proposal)


def test_accepts_refactor_patch_at_limits(tmp_path: Path) -> None:
    policy = GovernancePolicy(
        ProjectConfig(repository_root=tmp_path, target_module="src/calculator.py"),
        max_patch_bytes=5,
        max_patch_lines=2,
    )
    proposal = RefactorProposal(
        path="src/calculator.py",
        patch="\u00e9\nab",
        reason="boundary",
        risk="low",
    )

    assert policy.validate_refactor_proposal(proposal) == (
        tmp_path / "src" / "calculator.py"
    )


@pytest.mark.parametrize(
    ("usage", "message"),
    [
        (BudgetUsage(attempts=5), "attempt budget"),
        (BudgetUsage(llm_calls=6), "LLM-call budget"),
        (BudgetUsage(active_seconds=2700), "active-time budget"),
        (BudgetUsage(mutants=100), "mutant budget"),
    ],
)
def test_rejects_usage_at_default_budget_limit(
    policy: GovernancePolicy, usage: BudgetUsage, message: str
) -> None:
    with pytest.raises(PolicyViolation, match=message):
        policy.validate_budget(usage, TaskBudget())


def test_accepts_usage_below_all_budget_limits(policy: GovernancePolicy) -> None:
    usage = BudgetUsage(attempts=4, llm_calls=5, active_seconds=2699, mutants=99)

    assert policy.validate_budget(usage, TaskBudget()) is None


@pytest.mark.parametrize(
    ("usage", "message"),
    [
        (BudgetUsage(attempts=6), "attempt budget"),
        (BudgetUsage(llm_calls=7), "LLM-call budget"),
        (BudgetUsage(active_seconds=2701), "active-time budget"),
        (BudgetUsage(mutants=101), "mutant budget"),
    ],
)
def test_rejects_usage_over_default_budget_limit(
    policy: GovernancePolicy, usage: BudgetUsage, message: str
) -> None:
    with pytest.raises(PolicyViolation, match=message):
        policy.validate_budget(usage, TaskBudget())
