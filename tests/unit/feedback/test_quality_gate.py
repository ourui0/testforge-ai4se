"""Tests for QualityGate — ordered quality decisions."""

import pytest
from pydantic import ValidationError

from testforge.feedback.quality_gate import QualityDecision, QualityGate
from tests.unit.feedback.conftest import make_snapshot as _snap

# ── mutation-gate tests (from brief) ─────────────────────────────────

def test_mutation_gate_requires_new_kill_and_five_points(gate: QualityGate) -> None:
    """A valid mutation improvement: at least one new kill and score delta >= 5."""
    baseline = _snap(branch_coverage=70, mutants_total=20, mutants_killed=10, mutants_survived=10)
    candidate = _snap(branch_coverage=70, mutants_total=20, mutants_killed=11, mutants_survived=9)
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is True
    assert decision.reason == "mutation_improved"


def test_timeout_does_not_activate_coverage_fallback(gate: QualityGate) -> None:
    """Timeout status always returns mutation_tool_error, never coverage fallback."""
    baseline = _snap(branch_coverage=70, mutation_status="timeout")
    candidate = _snap(branch_coverage=80, mutation_status="timeout")
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "mutation_tool_error"


def test_mutation_error_returns_tool_error(gate: QualityGate) -> None:
    """Error status always returns mutation_tool_error."""
    baseline = _snap(branch_coverage=70, mutation_status="error")
    candidate = _snap(branch_coverage=80, mutation_status="error")
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "mutation_tool_error"


# ── zero-mutant fallback ─────────────────────────────────────────────

def test_zero_valid_mutants_with_supported_status_uses_coverage_fallback(
    gate: QualityGate,
) -> None:
    """Supported status but zero total mutants → coverage fallback."""
    baseline = _snap(branch_coverage=70, mutants_total=0, mutants_killed=0, mutants_survived=0)
    candidate = _snap(branch_coverage=76, mutants_total=0, mutants_killed=0, mutants_survived=0)
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is True
    assert decision.reason == "coverage_improved"


def test_zero_valid_mutants_coverage_fallback_fails_when_insufficient(
    gate: QualityGate,
) -> None:
    """Coverage fallback fails when coverage delta is below threshold."""
    baseline = _snap(branch_coverage=70, mutants_total=0, mutants_killed=0, mutants_survived=0)
    candidate = _snap(branch_coverage=72, mutants_total=0, mutants_killed=0, mutants_survived=0)
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "no_improvement"


# ── unsupported mutation fallback ────────────────────────────────────

def test_unsupported_mutation_uses_coverage_fallback(gate: QualityGate) -> None:
    """Explicitly unsupported mutation → coverage fallback."""
    baseline = _snap(branch_coverage=70, mutation_status="unsupported")
    candidate = _snap(branch_coverage=76, mutation_status="unsupported")
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is True
    assert decision.reason == "coverage_improved"


def test_unsupported_mutation_crosses_target_passes(gate: QualityGate) -> None:
    """Coverage fallback passes when crossing the configured target."""
    baseline = _snap(branch_coverage=88, mutation_status="unsupported")
    candidate = _snap(branch_coverage=91, mutation_status="unsupported")
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is True
    assert decision.reason == "coverage_improved"


def test_unsupported_mutation_fails_without_coverage_improvement(
    gate: QualityGate,
) -> None:
    """No coverage improvement → rejected."""
    baseline = _snap(branch_coverage=70, mutation_status="unsupported")
    candidate = _snap(branch_coverage=72, mutation_status="unsupported")
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "no_improvement"


# ── test regressions (checked first) ─────────────────────────────────

def test_fewer_passing_tests_is_regression(gate: QualityGate) -> None:
    """Fewer passing tests → test_regression, even if coverage improved."""
    baseline = _snap(tests_passed=50, tests_failed=0)
    candidate = _snap(tests_passed=49, tests_failed=1, branch_coverage=90)
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "test_regression"


def test_more_failed_tests_is_regression(gate: QualityGate) -> None:
    """More failed tests → test_regression."""
    baseline = _snap(tests_passed=50, tests_failed=0)
    candidate = _snap(tests_passed=50, tests_failed=1)
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "test_regression"


def test_more_skipped_tests_is_regression(gate: QualityGate) -> None:
    """More skipped tests → test_regression."""
    baseline = _snap(tests_passed=50, tests_skipped=0)
    candidate = _snap(tests_passed=50, tests_skipped=1)
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "test_regression"


# ── metric regression (checked second) ───────────────────────────────

def test_coverage_drop_is_metric_regression(gate: QualityGate) -> None:
    """Branch coverage dropping is a metric regression."""
    baseline = _snap(branch_coverage=70)
    candidate = _snap(branch_coverage=60)
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "metric_regression"


def test_mutation_score_drop_is_metric_regression(gate: QualityGate) -> None:
    """Mutation score dropping is a metric regression."""
    baseline = _snap(mutants_total=20, mutants_killed=10, mutants_survived=10)
    candidate = _snap(mutants_total=20, mutants_killed=8, mutants_survived=12)
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "metric_regression"


# ── no improvement ───────────────────────────────────────────────────

def test_no_new_kill_is_no_improvement(gate: QualityGate) -> None:
    """Same number of kills → no improvement."""
    baseline = _snap(mutants_total=20, mutants_killed=10, mutants_survived=10)
    candidate = _snap(mutants_total=20, mutants_killed=10, mutants_survived=10)
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "no_improvement"


def test_insufficient_score_delta_is_no_improvement(gate: QualityGate) -> None:
    """New kill but score delta below threshold → no improvement."""
    baseline = _snap(mutants_total=20, mutants_killed=10, mutants_survived=10)
    candidate = _snap(mutants_total=21, mutants_killed=11, mutants_survived=10)
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "no_improvement"


# ── strict gate regression before improvement ────────────────────────

def test_strict_gate_regression_checked_before_improvement(
    strict_gate: QualityGate,
) -> None:
    """Even with zero thresholds, test regression is rejected first."""
    baseline = _snap(tests_passed=50, tests_failed=0)
    candidate = _snap(tests_passed=48, tests_failed=2, branch_coverage=99)
    decision = strict_gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "test_regression"


def test_strict_gate_allows_any_improvement(strict_gate: QualityGate) -> None:
    """With zero thresholds, any new kill passes."""
    baseline = _snap(mutants_total=20, mutants_killed=10, mutants_survived=10)
    candidate = _snap(mutants_total=20, mutants_killed=11, mutants_survived=9)
    decision = strict_gate.evaluate(baseline, candidate)
    assert decision.passed is True
    assert decision.reason == "mutation_improved"


# ── QualityDecision model ────────────────────────────────────────────

def test_quality_decision_is_frozen() -> None:
    """QualityDecision must be immutable."""
    decision = QualityDecision(passed=True, reason="mutation_improved")
    with pytest.raises(ValidationError):
        decision.passed = False  # type: ignore[misc]


def test_quality_decision_requires_valid_reason() -> None:
    """QualityDecision rejects unknown reason values."""
    with pytest.raises(ValidationError):
        QualityDecision(passed=True, reason="bogus_reason")
