from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class TaskBudget(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_attempts: int = Field(default=5, ge=1, le=20)
    max_llm_calls: int = Field(default=6, ge=1, le=30)
    max_active_seconds: int = Field(default=2700, ge=60, le=14400)
    command_timeout_seconds: int = Field(default=60, ge=1, le=600)
    mutation_timeout_seconds: int = Field(default=600, ge=10, le=3600)
    max_mutants: int = Field(default=100, ge=1, le=1000)


class QualityThreshold(BaseModel):
    model_config = ConfigDict(frozen=True)
    mutation_delta_points: float = Field(default=5.0, ge=0, le=100)
    coverage_delta_points: float = Field(default=5.0, ge=0, le=100)
    coverage_target_percent: float = Field(default=90.0, ge=0, le=100)


class ProjectConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    repository_root: Path
    target_module: str
    tests_root: Path = Path("tests")
    sandbox_image: str | None = None
    dependency_fingerprint: str | None = None
    budget: TaskBudget = TaskBudget()
    quality: QualityThreshold = QualityThreshold()
