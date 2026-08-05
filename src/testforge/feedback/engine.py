"""Feedback engine — deterministic failure classification and stagnation detection."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from testforge.config import QualityThreshold
from testforge.domain.models import AttemptSummary, FeedbackPacket, MetricSnapshot
from testforge.feedback.quality_gate import QualityGate

# ── category precedence (lower = higher priority) ────────────────────

_CATEGORY_PRECEDENCE: dict[str, int] = {
    "syntax_error": 0,
    "import_error": 0,
    "assertion_failure": 0,
    "fixture_mock_error": 0,
    "timeout": 1,
    "flaky": 1,
    "surviving_mutant": 2,
    "coverage_not_improved": 3,
    "threshold_missed": 4,
}

_ALL_CATEGORIES = tuple(_CATEGORY_PRECEDENCE.keys())

# ── models ───────────────────────────────────────────────────────────


class FailureSignal(BaseModel):
    """Structured, sanitized failure signal for deterministic classification."""

    model_config = ConfigDict(frozen=True)

    category: Literal[_ALL_CATEGORIES]  # type: ignore[valid-type]
    summary: str = Field(min_length=1)


# ── constraint templates ─────────────────────────────────────────────

_CONSTRAINTS: dict[str, tuple[str, ...]] = {
    "syntax_error": ("fix syntax errors before re-evaluation",),
    "import_error": ("resolve import errors before re-evaluation",),
    "assertion_failure": (
        "strengthen assertion coverage for the failing test",
        "verify test expectations match the intended behaviour",
    ),
    "fixture_mock_error": (
        "repair test fixtures and mock setup before re-evaluation",
    ),
    "timeout": ("reduce test runtime or split long-running tests",),
    "flaky": (
        "stabilise flaky tests with deterministic setup",
        "isolate ordering-dependent assertions",
    ),
    "surviving_mutant": (
        "improve assertion coverage to catch surviving mutants",
        "add boundary-value assertions for the mutated region",
    ),
    "coverage_not_improved": (
        "add tests for uncovered branches",
        "target the lowest-covered modules first",
    ),
    "threshold_missed": (
        "improve test quality: more assertions, edge cases, or mutation kills",
    ),
}

# ── engine ───────────────────────────────────────────────────────────


class FeedbackEngine:
    """Deterministic feedback classification.

    Priority order (highest first):
      1. tool/test failure (syntax, import, assertion, fixture/mock)
      2. flaky / timeout
      3. surviving mutant
      4. coverage-not-improved
      5. generic threshold-missed

    Stagnation: two consecutive rounds with identical branch_coverage
    AND mutation_score.
    """

    def __init__(self, threshold: QualityThreshold) -> None:
        self._threshold = threshold
        self._gate = QualityGate(threshold)

    def build(
        self,
        baseline: MetricSnapshot,
        candidate: MetricSnapshot,
        surviving_mutants: tuple[str, ...] = (),
        prior_attempts: list[AttemptSummary] | None = None,
        candidate_failures: tuple[FailureSignal, ...] = (),
    ) -> FeedbackPacket:
        prior = prior_attempts or []

        # 1. Determine dominant category
        category = self._dominant_category(
            baseline, candidate, surviving_mutants, candidate_failures
        )

        # 2. Build constraints
        constraints = self._constraints_for(category)

        # 3. Detect stagnation: current candidate vs latest prior
        stagnated = self._is_stagnated(candidate, prior)

        return FeedbackPacket(
            failure_category=category,
            surviving_mutants=surviving_mutants,
            constraints_for_next_attempt=constraints,
            stagnated=stagnated,
        )

    # ── internal ──────────────────────────────────────────────────

    @staticmethod
    def _dominant_category(
        baseline: MetricSnapshot,
        candidate: MetricSnapshot,
        surviving_mutants: tuple[str, ...],
        candidate_failures: tuple[FailureSignal, ...],
    ) -> str:
        best_priority = 999
        best_category = "threshold_missed"

        # Check structured failure signals
        for sig in candidate_failures:
            pri = _CATEGORY_PRECEDENCE.get(sig.category, 999)
            if pri < best_priority:
                best_priority = pri
                best_category = sig.category

        # Surviving mutants signal
        if surviving_mutants:
            pri = _CATEGORY_PRECEDENCE["surviving_mutant"]
            if pri < best_priority:
                best_priority = pri
                best_category = "surviving_mutant"

        # Coverage / threshold fallback from gate evaluation
        decision = QualityGate(QualityThreshold()).evaluate(baseline, candidate)
        if decision.reason == "no_improvement":
            # Determine if this is coverage-not-improved or threshold-missed
            mutation_available = (
                candidate.mutation_status == "supported"
                and candidate.mutants_total > 0
            )
            if not mutation_available:
                pri = _CATEGORY_PRECEDENCE["coverage_not_improved"]
                if pri < best_priority:
                    best_category = "coverage_not_improved"
            else:
                pri = _CATEGORY_PRECEDENCE["threshold_missed"]
                if pri < best_priority:
                    best_category = "threshold_missed"

        return best_category

    @staticmethod
    def _constraints_for(category: str) -> tuple[str, ...]:
        return _CONSTRAINTS.get(category, _CONSTRAINTS["threshold_missed"])

    @staticmethod
    def _is_stagnated(
        candidate: MetricSnapshot,
        prior_attempts: list[AttemptSummary],
    ) -> bool:
        if not prior_attempts:
            return False
        latest = prior_attempts[-1]
        return (
            candidate.branch_coverage == latest.branch_coverage
            and candidate.mutation_score == latest.mutation_score
        )
