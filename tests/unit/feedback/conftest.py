"""Shared fixtures for feedback tests."""

import pytest

from testforge.config import QualityThreshold
from testforge.domain.models import AttemptSummary, MetricSnapshot
from testforge.feedback.engine import FeedbackEngine


def make_snapshot(**overrides) -> MetricSnapshot:
    """Build a MetricSnapshot with sensible mutation-gate defaults."""
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


@pytest.fixture
def gate():
    from testforge.feedback.quality_gate import QualityGate

    return QualityGate(QualityThreshold())


@pytest.fixture
def strict_gate():
    from testforge.feedback.quality_gate import QualityGate

    return QualityGate(
        QualityThreshold(
            mutation_delta_points=0.0,
            coverage_delta_points=0.0,
            coverage_target_percent=100.0,
        )
    )


@pytest.fixture
def engine() -> FeedbackEngine:
    return FeedbackEngine(QualityThreshold())


def make_attempt(
    branch_coverage: float = 70.0, mutation_score: float = 50.0
) -> AttemptSummary:
    return AttemptSummary(
        branch_coverage=branch_coverage, mutation_score=mutation_score
    )
