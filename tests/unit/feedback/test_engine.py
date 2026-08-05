"""Tests for FeedbackEngine — category classification and stagnation detection."""

import pytest
from pydantic import ValidationError

from testforge.config import QualityThreshold
from testforge.domain.models import AttemptSummary, MetricSnapshot
from testforge.feedback.engine import FailureSignal, FeedbackEngine

# ── helpers ──────────────────────────────────────────────────────────

def _snap(**overrides) -> MetricSnapshot:
    defaults = {
        "tests_passed": 50,
        "tests_failed": 0,
        "tests_skipped": 0,
        "branch_coverage": 70.0,
        "mutants_total": 20,
        "mutants_killed": 10,
        "mutants_survived": 10,
        "mutation_status": "supported",
    }
    defaults.update(overrides)
    return MetricSnapshot(**defaults)


def _attempt(branch_coverage: float = 70.0, mutation_score: float = 50.0) -> AttemptSummary:
    return AttemptSummary(branch_coverage=branch_coverage, mutation_score=mutation_score)


@pytest.fixture
def engine() -> FeedbackEngine:
    return FeedbackEngine(QualityThreshold())


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
