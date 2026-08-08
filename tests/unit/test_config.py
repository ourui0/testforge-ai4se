import pytest
from pydantic import ValidationError

from testforge.config import ProjectConfig, TaskBudget


def test_project_config_has_spec_defaults(tmp_path):
    config = ProjectConfig(repository_root=tmp_path, target_module="src/calculator.py")
    assert config.budget.max_attempts == 5
    assert config.budget.max_llm_calls == 6
    assert config.budget.max_active_seconds == 2700
    assert config.budget.max_mutants == 100
    assert config.quality.mutation_delta_points == 5.0
    assert config.quality.coverage_delta_points == 5.0
    assert config.quality.coverage_target_percent == 90.0


@pytest.mark.parametrize(
    "field,value",
    [("max_attempts", 0), ("max_llm_calls", 31), ("max_mutants", -1)],
)
def test_budget_rejects_invalid_bounds(field, value):
    with pytest.raises(ValidationError):
        TaskBudget(**{field: value})
