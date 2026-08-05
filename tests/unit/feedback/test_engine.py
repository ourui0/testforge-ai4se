"""Tests for FeedbackEngine — category classification and stagnation detection."""

import pytest
from pydantic import ValidationError

from testforge.config import QualityThreshold
from testforge.feedback.engine import FailureSignal, FeedbackEngine
from tests.unit.feedback.conftest import make_attempt as _attempt
from tests.unit.feedback.conftest import make_snapshot as _snap

# ── FailureSignal model ──────────────────────────────────────────────

def test_failure_signal_is_frozen() -> None:
    """FailureSignal must be immutable."""
    signal = FailureSignal(category="surviving_mutant", summary="mutant survived: x -> y")
    with pytest.raises(ValidationError):
        signal.category = "flaky"  # type: ignore[misc]


def test_failure_signal_rejects_unknown_category() -> None:
    """FailureSignal rejects invalid category values."""
    with pytest.raises(ValidationError):
        FailureSignal(category="made_up_category", summary="test")  # type: ignore[arg-type]


def test_failure_signal_summary_is_required() -> None:
    """Summary must not be empty."""
    with pytest.raises(ValidationError):
        FailureSignal(category="flaky", summary="")


# ── surviving-mutant feedback (from brief) ───────────────────────────

def test_surviving_mutant_feedback_names_mutant_and_constraint(
    engine: FeedbackEngine,
) -> None:
    """Surviving mutant → category + mutant names + assertion constraint."""
    baseline = _snap()
    candidate = _snap()  # same metrics → won't pass mutation gate
    packet = engine.build(
        baseline,
        candidate,
        surviving_mutants=("src/calc.py:12:+ -> -",),
        prior_attempts=[],
        candidate_failures=(),
    )
    assert packet.failure_category == "surviving_mutant"
    assert packet.surviving_mutants == ("src/calc.py:12:+ -> -",)
    assert any("assertion" in c for c in packet.constraints_for_next_attempt)


# ── category precedence ──────────────────────────────────────────────

def test_tool_failure_has_highest_precedence(engine: FeedbackEngine) -> None:
    """Test/tool failure beats all other signals."""
    baseline = _snap(tests_passed=50, tests_failed=0)
    candidate = _snap(tests_passed=48, tests_failed=2)
    packet = engine.build(
        baseline,
        candidate,
        surviving_mutants=("src/x.py:1:a->b",),
        candidate_failures=(
            FailureSignal(category="syntax_error", summary="SyntaxError in test_x.py"),
        ),
    )
    assert packet.failure_category == "syntax_error"


def test_flaky_beats_surviving_mutant(engine: FeedbackEngine) -> None:
    """Flaky/timeout beats surviving mutant."""
    baseline = _snap()
    candidate = _snap()
    packet = engine.build(
        baseline,
        candidate,
        surviving_mutants=("src/x.py:1:a->b",),
        candidate_failures=(
            FailureSignal(category="surviving_mutant", summary="mutant survived"),
            FailureSignal(category="flaky", summary="test flaked"),
        ),
    )
    assert packet.failure_category == "flaky"


def test_surviving_mutant_beats_coverage(engine: FeedbackEngine) -> None:
    """Surviving mutant beats coverage-not-improved."""
    baseline = _snap(branch_coverage=70, mutation_status="unsupported")
    candidate = _snap(branch_coverage=72, mutation_status="unsupported")
    packet = engine.build(
        baseline,
        candidate,
        surviving_mutants=("src/x.py:1:a->b",),
    )
    assert packet.failure_category == "surviving_mutant"


def test_coverage_beats_threshold(engine: FeedbackEngine) -> None:
    """Coverage-not-improved beats generic threshold-missed."""
    baseline = _snap(branch_coverage=70, mutation_status="unsupported")
    candidate = _snap(branch_coverage=72, mutation_status="unsupported")
    packet = engine.build(
        baseline,
        candidate,
    )
    assert packet.failure_category == "coverage_not_improved"


# ── individual categories ────────────────────────────────────────────

def test_assertion_failure_category(engine: FeedbackEngine) -> None:
    """Assertion failure is classified correctly."""
    baseline = _snap(tests_passed=50, tests_failed=0)
    candidate = _snap(tests_passed=49, tests_failed=1)
    packet = engine.build(
        baseline,
        candidate,
        candidate_failures=(
            FailureSignal(category="assertion_failure", summary="assert 1 == 2"),
        ),
    )
    assert packet.failure_category == "assertion_failure"


def test_timeout_category(engine: FeedbackEngine) -> None:
    """Timeout is classified as a distinct category."""
    baseline = _snap()
    candidate = _snap()
    packet = engine.build(
        baseline,
        candidate,
        candidate_failures=(
            FailureSignal(category="timeout", summary="test timed out after 30s"),
        ),
    )
    assert packet.failure_category == "timeout"


def test_import_error_category(engine: FeedbackEngine) -> None:
    """Import error is classified correctly."""
    baseline = _snap(tests_passed=50, tests_failed=0)
    candidate = _snap(tests_passed=10, tests_failed=0)
    packet = engine.build(
        baseline,
        candidate,
        candidate_failures=(
            FailureSignal(category="import_error", summary="ModuleNotFoundError: numpy"),
        ),
    )
    assert packet.failure_category == "import_error"
    assert any("import" in c for c in packet.constraints_for_next_attempt)


def test_fixture_mock_error_category(engine: FeedbackEngine) -> None:
    """Fixture/mock error is classified correctly."""
    baseline = _snap(tests_passed=50, tests_failed=0)
    candidate = _snap(tests_passed=0, tests_failed=50)
    packet = engine.build(
        baseline,
        candidate,
        candidate_failures=(
            FailureSignal(
                category="fixture_mock_error",
                summary="fixture 'db_connection' not found",
            ),
        ),
    )
    assert packet.failure_category == "fixture_mock_error"
    assert any("fixture" in c for c in packet.constraints_for_next_attempt)


def test_flaky_category(engine: FeedbackEngine) -> None:
    """Flaky test is classified correctly."""
    baseline = _snap()
    candidate = _snap()
    packet = engine.build(
        baseline,
        candidate,
        candidate_failures=(
            FailureSignal(category="flaky", summary="test passed on retry"),
        ),
    )
    assert packet.failure_category == "flaky"
    assert any("flaky" in c or "stabilis" in c for c in packet.constraints_for_next_attempt)


def test_threshold_missed_fallback(engine: FeedbackEngine) -> None:
    """When no other signal, generic threshold-missed is used."""
    baseline = _snap(mutants_total=20, mutants_killed=10, mutants_survived=10)
    candidate = _snap(mutants_total=20, mutants_killed=10, mutants_survived=10)
    packet = engine.build(
        baseline,
        candidate,
        surviving_mutants=(),
        candidate_failures=(),
    )
    assert packet.failure_category == "threshold_missed"


def test_constraints_for_assertion_failure(engine: FeedbackEngine) -> None:
    """Assertion failure → constraint references the failing assertion."""
    baseline = _snap(tests_passed=50, tests_failed=0)
    candidate = _snap(tests_passed=49, tests_failed=1)
    packet = engine.build(
        baseline,
        candidate,
        candidate_failures=(
            FailureSignal(category="assertion_failure", summary="assert x == y"),
        ),
    )
    assert packet.failure_category == "assertion_failure"
    # Should have a meaningful constraint
    assert len(packet.constraints_for_next_attempt) > 0


def test_constraints_for_coverage(engine: FeedbackEngine) -> None:
    """Coverage not improved → constraint suggests branch coverage."""
    baseline = _snap(branch_coverage=70, mutation_status="unsupported")
    candidate = _snap(branch_coverage=72, mutation_status="unsupported")
    packet = engine.build(baseline, candidate)
    assert packet.failure_category == "coverage_not_improved"
    assert any("branch" in c for c in packet.constraints_for_next_attempt)


# ── stagnation ───────────────────────────────────────────────────────

def test_stagnation_two_consecutive_equal_rounds(engine: FeedbackEngine) -> None:
    """Two consecutive rounds with identical metrics → stagnated."""
    baseline = _snap(branch_coverage=70, mutants_total=20, mutants_killed=10, mutants_survived=10)
    candidate = _snap(branch_coverage=70, mutants_total=20, mutants_killed=10, mutants_survived=10)
    prior = [_attempt(branch_coverage=70.0, mutation_score=50.0)]
    packet = engine.build(baseline, candidate, prior_attempts=prior)
    assert packet.stagnated is True


def test_no_stagnation_with_different_coverage(engine: FeedbackEngine) -> None:
    """Different branch coverage → no stagnation."""
    baseline = _snap(branch_coverage=70)
    candidate = _snap(branch_coverage=75)
    prior = [_attempt(branch_coverage=70.0, mutation_score=50.0)]
    packet = engine.build(baseline, candidate, prior_attempts=prior)
    assert packet.stagnated is False


def test_no_stagnation_with_different_mutation_score(engine: FeedbackEngine) -> None:
    """Different mutation score → no stagnation."""
    baseline = _snap(mutants_total=20, mutants_killed=10, mutants_survived=10)
    candidate = _snap(mutants_total=20, mutants_killed=11, mutants_survived=9)
    prior = [_attempt(branch_coverage=70.0, mutation_score=50.0)]
    packet = engine.build(baseline, candidate, prior_attempts=prior)
    assert packet.stagnated is False


def test_stagnation_compares_current_candidate_with_latest_prior(
    engine: FeedbackEngine,
) -> None:
    """Stagnation compares current candidate vs latest prior, not two old priors."""
    baseline = _snap(branch_coverage=70, mutants_total=20, mutants_killed=10, mutants_survived=10)
    candidate = _snap(branch_coverage=70, mutants_total=20, mutants_killed=10, mutants_survived=10)
    # Latest prior matches candidate → stagnation
    prior = [
        _attempt(branch_coverage=65.0, mutation_score=45.0),
        _attempt(branch_coverage=70.0, mutation_score=50.0),
    ]
    packet = engine.build(baseline, candidate, prior_attempts=prior)
    assert packet.stagnated is True


def test_stagnation_no_prior_is_not_stagnated(engine: FeedbackEngine) -> None:
    """No prior attempts → never stagnated."""
    baseline = _snap(branch_coverage=70)
    candidate = _snap(branch_coverage=70)
    packet = engine.build(baseline, candidate, prior_attempts=[])
    assert packet.stagnated is False


# ── full packet from brief step 4 ─────────────────────────────────────

def test_feedback_packet_matches_brief_example(engine: FeedbackEngine) -> None:
    """The brief's example: surviving mutant names are forwarded."""
    baseline = _snap()
    candidate = _snap()
    packet = engine.build(
        baseline,
        candidate,
        surviving_mutants=("src/calc.py:12:+ -> -",),
        prior_attempts=[],
        candidate_failures=(),
    )
    assert packet.failure_category == "surviving_mutant"
    assert packet.surviving_mutants == ("src/calc.py:12:+ -> -",)
    assert "assertion" in packet.constraints_for_next_attempt[0]


# ── 0 prior—no stagnation, 1 prior exact match—stagnated from the start

def test_one_prior_equal_to_candidate_is_stagnated(engine: FeedbackEngine) -> None:
    """One prior exactly matches candidate → stagnated immediately."""
    baseline = _snap(branch_coverage=70, mutants_total=20, mutants_killed=10)
    candidate = _snap(branch_coverage=70, mutants_total=20, mutants_killed=10)
    prior = [_attempt(branch_coverage=70.0, mutation_score=50.0)]
    packet = engine.build(baseline, candidate, prior_attempts=prior)
    assert packet.stagnated is True


# ── F1 regression: engine respects configured thresholds ─────────────

def test_engine_uses_configured_not_default_threshold() -> None:
    """F1: _dominant_category must use self._gate, not QualityGate(QualityThreshold())."""
    strict_engine = FeedbackEngine(
        QualityThreshold(coverage_delta_points=10.0, coverage_target_percent=95.0)
    )
    baseline = _snap(branch_coverage=70, mutation_status="unsupported")
    candidate = _snap(branch_coverage=76, mutation_status="unsupported")  # delta=6

    # strict gate: delta 6 < threshold 10 and 76 < target 95 → no_improvement
    packet = strict_engine.build(baseline, candidate)
    # With the bug, the default gate (delta=5) sees 6 >= 5 → coverage_improved,
    # so the engine never enters the no_improvement branch and returns
    # threshold_missed instead of coverage_not_improved.
    assert packet.failure_category == "coverage_not_improved"


def test_engine_respects_coverage_target() -> None:
    """F1: engine with low delta but high target crossing should classify correctly."""
    strict_engine = FeedbackEngine(
        QualityThreshold(coverage_delta_points=10.0, coverage_target_percent=90.0)
    )
    baseline = _snap(branch_coverage=85, mutation_status="unsupported")
    candidate = _snap(branch_coverage=91, mutation_status="unsupported")  # delta=6 < 10 but crosses 90 target

    # strict gate: 91 >= target 90 → coverage_improved (passes gate)
    # Since gate passes, no no_improvement → surviving_mutant or threshold
    # But no surviving mutants and no failures → threshold_missed
    packet = strict_engine.build(baseline, candidate)
    # Gate passes → no no_improvement, no surviving_mutants, no failures → threshold_missed
    assert packet.failure_category == "threshold_missed"
