"""Quality gate with ordered regression checks and mutation/coverage fallback."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from testforge.config import QualityThreshold
from testforge.domain.models import MetricSnapshot


def is_mutation_available(snapshot: MetricSnapshot) -> bool:
    """Return True when valid mutation data is available for gating."""
    return snapshot.mutation_status == "supported" and snapshot.mutants_total > 0


class QualityDecision(BaseModel):
    """Immutable pass/fail decision with a fixed reason."""

    model_config = ConfigDict(frozen=True)

    passed: bool
    reason: Literal[
        "mutation_improved",
        "coverage_improved",
        "test_regression",
        "metric_regression",
        "mutation_tool_error",
        "no_improvement",
    ]


class QualityGate:
    """Ordered quality evaluation.

    1. Test/skip regressions — reject immediately.
    2. Metric regressions — reject second.
    3. Mutation tool error (timeout/error) — reject, never fallback.
    4. Valid mutation data → require ≥1 new kill and score-delta threshold.
    5. Unsupported / zero-mutant → coverage fallback (delta or target).
    6. Otherwise → no improvement.
    """

    def __init__(self, threshold: QualityThreshold) -> None:
        self._threshold = threshold

    def evaluate(
        self, baseline: MetricSnapshot, candidate: MetricSnapshot
    ) -> QualityDecision:
        # 1. Test/skip regressions
        if candidate.tests_passed < baseline.tests_passed:
            return QualityDecision(passed=False, reason="test_regression")
        if candidate.tests_failed > baseline.tests_failed:
            return QualityDecision(passed=False, reason="test_regression")
        if candidate.tests_skipped > baseline.tests_skipped:
            return QualityDecision(passed=False, reason="test_regression")

        # 2. Metric regressions
        if candidate.branch_coverage < baseline.branch_coverage:
            return QualityDecision(passed=False, reason="metric_regression")
        if candidate.mutation_score < baseline.mutation_score:
            return QualityDecision(passed=False, reason="metric_regression")

        # 3. Mutation tool error — never fallback
        if candidate.mutation_status in ("timeout", "error"):
            return QualityDecision(passed=False, reason="mutation_tool_error")

        # 4. Determine whether valid mutation data is available
        if is_mutation_available(candidate):
            return self._evaluate_mutation(baseline, candidate)

        # 5. Coverage fallback (unsupported or zero valid mutants)
        return self._evaluate_coverage_fallback(baseline, candidate)

    def _evaluate_mutation(
        self, baseline: MetricSnapshot, candidate: MetricSnapshot
    ) -> QualityDecision:
        new_kills = candidate.mutants_killed - baseline.mutants_killed
        score_delta = candidate.mutation_score - baseline.mutation_score

        if new_kills > 0 and score_delta >= self._threshold.mutation_delta_points:
            return QualityDecision(passed=True, reason="mutation_improved")

        return QualityDecision(passed=False, reason="no_improvement")

    def _evaluate_coverage_fallback(
        self, baseline: MetricSnapshot, candidate: MetricSnapshot
    ) -> QualityDecision:
        coverage_delta = candidate.branch_coverage - baseline.branch_coverage

        if (
            coverage_delta >= self._threshold.coverage_delta_points
            or candidate.branch_coverage >= self._threshold.coverage_target_percent
        ):
            return QualityDecision(passed=True, reason="coverage_improved")

        return QualityDecision(passed=False, reason="no_improvement")
