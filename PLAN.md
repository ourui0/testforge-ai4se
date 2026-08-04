# TestForge Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python Coding Agent Harness that generates high-value pytest unit tests through a deterministic coverage-and-mutation feedback loop, with Docker isolation and human approval before real repository changes.

**Architecture:** A modular monolith exposes one application service to a Typer CLI and FastAPI/HTMX UI. A persisted finite-state `AgentEngine` coordinates a provider-neutral LLM adapter, domain-only tools, deterministic feedback/quality gates, project memory, governance policies, and a Docker sandbox; the public demo swaps real execution and LLM access for fixtures and scripted mocks.

**Tech Stack:** Python 3.11+ (Python 3.12 in release containers), Pydantic, Typer, FastAPI, Jinja2/HTMX, SQLAlchemy + SQLite, keyring, OpenAI SDK, Docker SDK, pytest, coverage.py, mutmut, Ruff, mypy.

## Global Constraints

- Implement the Agent loop, action parsing, tool dispatch, feedback, memory, governance, approval, and stopping logic in repository code; do not use an Agent Runner or high-level agent framework.
- Support one user-selected Python file or module per task and generate pytest unit tests only.
- Do not expose arbitrary Shell, Docker, filesystem, or network tools to the LLM.
- Production source is read-only by default; each refactor proposal and final test write-back requires human approval bound to an exact patch hash.
- Run candidate code in a non-root Docker sandbox with networking disabled, CPU/memory/process/time limits, no Docker socket, no home directory, and no credential mounts.
- Default budget: 5 generation attempts, 6 LLM calls, 45 minutes active execution, 60 seconds per pytest/coverage call, 10 minutes per mutation run, and at most 100 mutants.
- Candidate tests must not regress existing pytest, skip, branch coverage, or mutation results.
- With valid surviving mutants, success requires at least one newly killed mutant and a mutation-score increase of at least 5 percentage points.
- With zero valid mutants or an explicit unsupported result, success requires branch coverage to increase by 5 percentage points or rise from below 90% to at least 90%; tool crashes and timeouts do not activate this fallback.
- Store project configuration, baselines, attempt summaries, failure classes, and approvals as structured memory; do not store complete source, complete prompts, secrets, or raw unredacted logs.
- Use the OS keyring by default. `.env` is an explicit development fallback, is Git-ignored, and must be documented as plaintext.
- The public WebUI uses bundled fixtures and `MockLLMClient` only; it accepts no code upload, repository URL, or API key.
- Follow strict TDD for every task: observe RED, implement the minimum for GREEN, refactor under passing tests, run task tests, then run the full fast suite.
- Every task receives spec-compliance review before code-quality review. Critical findings block the next task.
- Never include a real credential in a test, fixture, command, log, commit, or screenshot.

## Execution Environment Bootstrap

Complete this once before Task 1. Python 3.11 is the minimum supported interpreter. Python pattern matching is not a 3.12-only feature; the plan's first version selected 3.12 without a project-specific need, so a 3.11 environment is valid.

On Windows PowerShell:

```powershell
py -3.11 --version
py -3.11 -m venv .venv
$TestForgePython = (Resolve-Path ".venv\Scripts\python.exe").Path
& $TestForgePython --version
```

On POSIX:

```bash
python3.11 --version
python3.11 -m venv .venv
TESTFORGE_PYTHON=".venv/bin/python"
"$TESTFORGE_PYTHON" --version
```

Every later `python -m ...` command means the interpreter inside this `.venv`: use `& $TestForgePython -m ...` on Windows PowerShell or `"$TESTFORGE_PYTHON" -m ...` on POSIX. Do not silently fall back to a different global Python. A current Python 3.11 patch release is recommended for normal development, but Python 3.11.0 is sufficient for the cold-start Task 1 trial.

Verify repository state before Task 1:

```bash
git rev-parse --is-inside-work-tree
```

If this fails because the disposable cold-start directory is not a repository, initialize only that directory with `git init -b main`. Preserve any existing Git identity. Check it with `git config --get user.name` and `git config --get user.email`. If either value is missing in the disposable cold-start repository, use repository-local validation identity only:

```bash
git config --local user.name "TestForge Cold Start"
git config --local user.email "testforge-cold-start@example.invalid"
```

Do not modify global Git configuration. In the real project repository, a missing identity requires the human owner's identity instead of the validation identity.

Repository paths in this plan use `/` intentionally: Git, `.gitignore`, Python imports, and documentation use portable forward slashes. Runtime filesystem code must use `pathlib.Path`. The cold-start trial reproduced `PermissionError: [WinError 5]` under the user-level pytest temp directory, so pytest intentionally uses the ignored project-local `.pytest_tmp/` as `--basetemp`. Test execution is sequential; concurrent runs must not share this directory.

## Planned File Structure

```text
pyproject.toml                         Packaging, dependencies, test/lint/type configuration
src/testforge/config.py                Validated project, quality, and budget configuration
src/testforge/domain/models.py         Task, attempt, metrics, proposal, feedback, approval models
src/testforge/domain/errors.py         Stable domain error taxonomy
src/testforge/domain/state_machine.py  Pure task-state transition function
src/testforge/persistence/schema.py    SQLAlchemy tables
src/testforge/persistence/repository.py SQLite task/attempt/metric/audit repository
src/testforge/governance/policy.py     Path, action, patch-size, and budget policy
src/testforge/governance/approval.py   Hash-bound approval decisions
src/testforge/governance/apply.py      Atomic, stale-safe write-back
src/testforge/llm/protocol.py           LLM interface and validated response models
src/testforge/llm/mock.py               Scripted deterministic LLM
src/testforge/llm/openai_adapter.py     First real provider adapter
src/testforge/tools/results.py          Command and analyzer result models
src/testforge/tools/parsers.py          pytest/coverage/mutmut output parsers
src/testforge/sandbox/docker_runner.py  Restricted Docker execution
src/testforge/tools/dispatcher.py       Domain-only tool registry and dispatch
src/testforge/feedback/quality_gate.py  Relative quality decision
src/testforge/feedback/engine.py        Failure classification and FeedbackPacket creation
src/testforge/memory.py                 Structured project memory selection
src/testforge/engine.py                 Persisted single-candidate Agent state machine
src/testforge/application.py            CLI/Web use-case facade
src/testforge/credentials.py            Keyring and explicit dotenv fallback
src/testforge/cli.py                    Typer commands
src/testforge/web/app.py                FastAPI routes and demo-mode boundary
src/testforge/web/templates/            Server-rendered UI
src/testforge/demo.py                   Bundled fixture scenarios
scripts/mechanism_demo.py               Deterministic required mechanism demonstration
tests/                                  Unit, integration, end-to-end, and fixture projects
Dockerfile                              Web/demo image
.github/workflows/ci.yml                GitHub CI compatibility
.gitlab-ci.yml                          NJU Git/GitLab CI compatibility
README.md                               User, security, distribution, and limitation documentation
```

## Dependency and Parallelization Map

```text
Task 1 → Task 2 → Task 3
              ├─→ Task 4 → Task 5
              ├─→ Task 6
              ├─→ Task 7 → Task 8
              └─→ Task 9
Task 4 + Task 5 + Task 6 + Task 8 + Task 9 → Task 10 → Task 11 → Task 12
Task 3 → Task 13
Task 6 + Task 13 → Task 14
Task 12 + Task 13 → Task 15 → Task 16 → Task 17
Task 12 + Task 17 → Task 18
All prior tasks → Task 19
```

After Task 3, Tasks 4, 6, 7, and 9 can run in parallel worktrees. Task 13 can run in parallel with Tasks 4–12. Each task still receives its own PR and two-stage review.

---

### Task 1: Package Skeleton and Validated Configuration

> **Formal completion:** implementer `/root/task01_implementer`; task commit `f617cf7`; integration merge `313de8f`; RED observed before production code; focused/full suites `4 passed`; independent task review found no issues.

**Files:**
- Create: `pyproject.toml`
- Create: `src/testforge/__init__.py`
- Create: `src/testforge/config.py`
- Create: `tests/unit/test_config.py`
- Create: `.gitignore`

**Interfaces:**
- Consumes: none.
- Produces: `TaskBudget`, `QualityThreshold`, and `ProjectConfig` Pydantic models used by all later tasks.

- [x] **Step 1: Add packaging metadata and write the failing default-budget test**

```toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "testforge-harness"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.8,<3",
  "sqlalchemy>=2.0,<3",
  "typer>=0.12,<1",
  "fastapi>=0.115,<1",
  "jinja2>=3.1,<4",
  "itsdangerous>=2.2,<3",
  "python-multipart>=0.0.9,<1",
  "uvicorn>=0.30,<1",
  "keyring>=25,<26",
  "openai>=1.40,<3",
  "docker>=7,<8",
]

[project.optional-dependencies]
dev = ["build>=1.2,<2", "httpx>=0.27,<1", "pytest>=8,<9", "pytest-cov>=5,<7", "pytest-json-report>=1.5,<2", "mutmut>=3,<4", "ruff>=0.6,<1", "mypy>=1.11,<2"]

[tool.hatch.build.targets.wheel]
packages = ["src/testforge"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --basetemp=.pytest_tmp"
```

```python
# tests/unit/test_config.py
from testforge.config import ProjectConfig


def test_project_config_has_spec_defaults(tmp_path):
    config = ProjectConfig(repository_root=tmp_path, target_module="src/calculator.py")
    assert config.budget.max_attempts == 5
    assert config.budget.max_llm_calls == 6
    assert config.budget.max_active_seconds == 2700
    assert config.budget.max_mutants == 100
    assert config.quality.mutation_delta_points == 5.0
    assert config.quality.coverage_delta_points == 5.0
    assert config.quality.coverage_target_percent == 90.0
```

- [x] **Step 2: Install into the project virtual environment and verify RED**

Run with the `.venv` interpreter selected in **Execution Environment Bootstrap**: `python -m pip install -e ".[dev]"`

Run with that same interpreter: `python -m pytest tests/unit/test_config.py -v`

Expected: FAIL because `testforge.config` does not exist.

- [x] **Step 3: Implement validated immutable configuration**

```python
# src/testforge/config.py
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
```

- [x] **Step 4: Add invalid-budget cases and run GREEN**

```python
import pytest
from pydantic import ValidationError
from testforge.config import TaskBudget


@pytest.mark.parametrize("field,value", [("max_attempts", 0), ("max_llm_calls", 31), ("max_mutants", -1)])
def test_budget_rejects_invalid_bounds(field, value):
    with pytest.raises(ValidationError):
        TaskBudget(**{field: value})
```

Run: `python -m pytest tests/unit/test_config.py -v`  
Expected: PASS.

- [x] **Step 5: Add secret/build ignores and commit**

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
.pytest_tmp/
.coverage
htmlcov/
.mutmut-cache/
*.db
dist/
build/
```

Run: `git diff --check`  
Commit: `git add pyproject.toml src/testforge/__init__.py src/testforge/config.py tests/unit/test_config.py .gitignore && git commit -m "build: add validated project configuration"`

---

### Task 2: Domain Models and Pure State Machine

> **Approved clarifications:** (1) the original plan named shared outputs without schemas, so human approval added the minimal immutable contracts already consumed by Tasks 3–12; (2) task review found that a public mutable transition dictionary violates the pure, closed state-machine guarantee, so human approval requires a read-only `MappingProxyType` plus a mutation-rejection regression test.

> **Formal completion:** implementer `/root/task02_implementer`; commits `0003258`, `0d87095`; integration merge `29562a2`; RED observed for state machine, models, and immutable-transition regression; full suite `12 passed`; initial review finding fixed and scoped re-review clean.

**Files:**
- Create: `src/testforge/domain/__init__.py`
- Create: `src/testforge/domain/models.py`
- Create: `src/testforge/domain/errors.py`
- Create: `src/testforge/domain/state_machine.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/domain/test_state_machine.py`
- Create: `tests/unit/domain/test_models.py`

**Interfaces:**
- Consumes: `TaskBudget`, `QualityThreshold` from Task 1.
- Produces: `TaskState`, `TaskEvent`, `transition(state, event)`, `MetricSnapshot`, `TestProposal`, `RefactorProposal`, `FeedbackPacket`, `TaskRecord`, and stable domain errors.

- [x] **Step 1: Write failing transition tests**

```python
import pytest
from testforge.domain.state_machine import TRANSITIONS, TaskEvent, TaskState, transition


def test_evaluation_retries_when_budget_remains():
    assert transition(TaskState.EVALUATING, TaskEvent.QUALITY_MISSED) is TaskState.GENERATING


def test_refactor_request_pauses_for_approval():
    assert transition(TaskState.GENERATING, TaskEvent.REFACTOR_REQUESTED) is TaskState.AWAITING_REFACTOR_APPROVAL


def test_quality_pass_waits_for_apply_approval():
    assert transition(TaskState.EVALUATING, TaskEvent.QUALITY_PASSED) is TaskState.AWAITING_APPLY_APPROVAL


def test_transition_table_rejects_external_mutation():
    with pytest.raises(TypeError):
        TRANSITIONS[(TaskState.CREATED, TaskEvent.APPLY_SUCCEEDED)] = TaskState.COMPLETED
```

- [x] **Step 2: Run transition tests to verify RED**

Run: `python -m pytest tests/unit/domain/test_state_machine.py -v`  
Expected: FAIL because the domain package does not exist.

- [x] **Step 3: Implement enums, legal transition table, and illegal-transition error**

```python
# src/testforge/domain/state_machine.py
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping
from testforge.domain.errors import InvalidTransition


class TaskState(StrEnum):
    CREATED = "created"
    VALIDATING_INPUT = "validating_input"
    PREPARING_SANDBOX = "preparing_sandbox"
    BASELINING = "baselining"
    GENERATING = "generating"
    TESTING = "testing"
    MEASURING_COVERAGE = "measuring_coverage"
    MUTATION_TESTING = "mutation_testing"
    EVALUATING = "evaluating"
    AWAITING_REFACTOR_APPROVAL = "awaiting_refactor_approval"
    AWAITING_APPLY_APPROVAL = "awaiting_apply_approval"
    APPLYING_PATCH = "applying_patch"
    COMPLETED = "completed"
    NO_ACTION_NEEDED = "no_action_needed"
    STOPPED = "stopped"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"


class TaskEvent(StrEnum):
    START = "start"
    INPUT_VALID = "input_valid"
    SANDBOX_READY = "sandbox_ready"
    BASELINE_READY = "baseline_ready"
    PROPOSAL_READY = "proposal_ready"
    TESTS_FINISHED = "tests_finished"
    COVERAGE_FINISHED = "coverage_finished"
    MUTATION_FINISHED = "mutation_finished"
    QUALITY_MISSED = "quality_missed"
    QUALITY_PASSED = "quality_passed"
    REFACTOR_REQUESTED = "refactor_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    NO_GAP = "no_gap"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANCEL = "cancel"
    ERROR = "error"
    WORKSPACE_CHANGED = "workspace_changed"
    APPLY_SUCCEEDED = "apply_succeeded"


def transition(state: TaskState, event: TaskEvent) -> TaskState:
    key = (state, event)
    if key not in TRANSITIONS:
        raise InvalidTransition(state=state, event=event)
    return TRANSITIONS[key]


_TRANSITIONS: dict[tuple[TaskState, TaskEvent], TaskState] = {
    (TaskState.CREATED, TaskEvent.START): TaskState.VALIDATING_INPUT,
    (TaskState.VALIDATING_INPUT, TaskEvent.INPUT_VALID): TaskState.PREPARING_SANDBOX,
    (TaskState.PREPARING_SANDBOX, TaskEvent.SANDBOX_READY): TaskState.BASELINING,
    (TaskState.BASELINING, TaskEvent.BASELINE_READY): TaskState.GENERATING,
    (TaskState.BASELINING, TaskEvent.NO_GAP): TaskState.NO_ACTION_NEEDED,
    (TaskState.GENERATING, TaskEvent.PROPOSAL_READY): TaskState.TESTING,
    (TaskState.GENERATING, TaskEvent.REFACTOR_REQUESTED): TaskState.AWAITING_REFACTOR_APPROVAL,
    (TaskState.TESTING, TaskEvent.TESTS_FINISHED): TaskState.MEASURING_COVERAGE,
    (TaskState.MEASURING_COVERAGE, TaskEvent.COVERAGE_FINISHED): TaskState.MUTATION_TESTING,
    (TaskState.MUTATION_TESTING, TaskEvent.MUTATION_FINISHED): TaskState.EVALUATING,
    (TaskState.EVALUATING, TaskEvent.QUALITY_MISSED): TaskState.GENERATING,
    (TaskState.EVALUATING, TaskEvent.QUALITY_PASSED): TaskState.AWAITING_APPLY_APPROVAL,
    (TaskState.AWAITING_REFACTOR_APPROVAL, TaskEvent.APPROVED): TaskState.BASELINING,
    (TaskState.AWAITING_REFACTOR_APPROVAL, TaskEvent.REJECTED): TaskState.GENERATING,
    (TaskState.AWAITING_APPLY_APPROVAL, TaskEvent.APPROVED): TaskState.APPLYING_PATCH,
    (TaskState.AWAITING_APPLY_APPROVAL, TaskEvent.REJECTED): TaskState.STOPPED,
    (TaskState.APPLYING_PATCH, TaskEvent.APPLY_SUCCEEDED): TaskState.COMPLETED,
}

for active_state in set(TaskState) - {TaskState.COMPLETED, TaskState.NO_ACTION_NEEDED, TaskState.STOPPED, TaskState.FAILED, TaskState.CANCELLED}:
    _TRANSITIONS[(active_state, TaskEvent.CANCEL)] = TaskState.CANCELLED
    _TRANSITIONS[(active_state, TaskEvent.ERROR)] = TaskState.FAILED
    _TRANSITIONS[(active_state, TaskEvent.WORKSPACE_CHANGED)] = TaskState.STALE

for budgeted_state in {TaskState.GENERATING, TaskState.TESTING, TaskState.MEASURING_COVERAGE, TaskState.MUTATION_TESTING, TaskState.EVALUATING}:
    _TRANSITIONS[(budgeted_state, TaskEvent.BUDGET_EXHAUSTED)] = TaskState.STOPPED

TRANSITIONS: Mapping[tuple[TaskState, TaskEvent], TaskState] = MappingProxyType(_TRANSITIONS)
```

- [x] **Step 4: Write and implement validated domain model tests**

```python
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
    TestProposal,
)
from testforge.domain.state_machine import TaskState


def test_test_proposal_is_a_single_test_file_replacement():
    proposal = TestProposal(path="tests/test_math.py", content="def test_add():\n    assert 1 + 1 == 2\n", strategy="boundary assertion")
    assert proposal.path.startswith("tests/")


def test_metric_snapshot_computes_mutation_score():
    metrics = MetricSnapshot(tests_passed=4, tests_failed=0, tests_skipped=0, branch_coverage=75.0, mutants_total=4, mutants_killed=3, mutants_survived=1)
    assert metrics.mutation_score == 75.0


def test_shared_domain_contracts_have_safe_immutable_defaults():
    refactor = RefactorProposal(path="src/math.py", patch="@@ -1 +1 @@", reason="isolate clock", risk="low")
    feedback = FeedbackPacket(failure_category="surviving_mutant", surviving_mutants=("src/math.py:1",), constraints_for_next_attempt=("add a boundary assertion",))
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
```

Implement immutable Pydantic models and the errors `InputError`, `ConfigurationError`, `CredentialError`, `LLMError`, `SandboxError`, `ToolExecutionError`, `PolicyViolation`, `StaleWorkspaceError`, and `InvalidTransition`.

```python
class TestForgeError(Exception):
    pass


class InputError(TestForgeError):
    pass


class ConfigurationError(TestForgeError):
    pass


class CredentialError(TestForgeError):
    pass


class LLMError(TestForgeError):
    pass


class SandboxError(TestForgeError):
    pass


class ToolExecutionError(TestForgeError):
    pass


class PolicyViolation(TestForgeError):
    pass


class StaleWorkspaceError(TestForgeError):
    pass


class InvalidTransition(TestForgeError):
    def __init__(self, state: object, event: object) -> None:
        state_value = getattr(state, "value", str(state))
        event_value = getattr(event, "value", str(event))
        super().__init__(f"event {event_value} is invalid from state {state_value}")


class MetricSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    tests_passed: int = Field(ge=0)
    tests_failed: int = Field(ge=0)
    tests_skipped: int = Field(ge=0)
    branch_coverage: float = Field(ge=0, le=100)
    mutants_total: int = Field(ge=0)
    mutants_killed: int = Field(ge=0)
    mutants_survived: int = Field(ge=0)
    mutation_status: Literal["supported", "unsupported", "timeout", "error"] = "supported"

    @computed_field
    @property
    def mutation_score(self) -> float:
        return 0.0 if self.mutants_total == 0 else 100.0 * self.mutants_killed / self.mutants_total


class TestProposal(BaseModel):
    model_config = ConfigDict(frozen=True)
    path: str
    content: str
    strategy: str


class RefactorProposal(BaseModel):
    model_config = ConfigDict(frozen=True)
    path: str
    patch: str
    reason: str
    risk: str
    alternatives: tuple[str, ...] = ()


class FeedbackPacket(BaseModel):
    model_config = ConfigDict(frozen=True)
    failure_category: str = Field(min_length=1)
    surviving_mutants: tuple[str, ...] = ()
    constraints_for_next_attempt: tuple[str, ...] = ()
    stagnated: bool = False


class BudgetUsage(BaseModel):
    model_config = ConfigDict(frozen=True)
    attempts: int = Field(default=0, ge=0)
    llm_calls: int = Field(default=0, ge=0)
    active_seconds: int = Field(default=0, ge=0)
    mutants: int = Field(default=0, ge=0)

    def exhausted(self, budget: TaskBudget) -> bool:
        return (
            self.attempts >= budget.max_attempts
            or self.llm_calls >= budget.max_llm_calls
            or self.active_seconds >= budget.max_active_seconds
            or self.mutants >= budget.max_mutants
        )


class AttemptSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    branch_coverage: float = Field(ge=0, le=100)
    mutation_score: float = Field(ge=0, le=100)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    kind: Literal["refactor", "apply_tests"]
    patch_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ApprovalStatus = ApprovalStatus.PENDING
    actor: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None
    expires_at: datetime | None = None


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    event_type: str = Field(min_length=1)
    reason: str
    occurred_at: datetime = Field(default_factory=utc_now)


class TaskRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    target_module: str = Field(min_length=1)
    state: TaskState = TaskState.CREATED
    budget: TaskBudget = TaskBudget()
    quality: QualityThreshold = QualityThreshold()
    usage: BudgetUsage = BudgetUsage()
    baseline_metrics: MetricSnapshot | None = None
    latest_metrics: MetricSnapshot | None = None
    pending_patch: str | None = None
    memory_tags: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    attempt_summaries: tuple[AttemptSummary, ...] = ()
    surviving_mutants: tuple[str, ...] = ()


class TransitionResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    previous_state: TaskState
    current_state: TaskState
    blocked: bool
    reason: str
```

The model module imports `datetime`, `timezone`, `UUID`, `uuid4`, `Literal`, `TaskBudget`, `QualityThreshold`, and `TaskState`; define `utc_now()` as `datetime.now(timezone.utc)`. These value objects are contracts only: Task 2 does not implement repositories, approval decisions, feedback algorithms, or engine behavior.

- [x] **Step 5: Run domain tests and commit**

Run: `python -m pytest tests/unit/domain -v`  
Expected: PASS.  
Commit: `git add src/testforge/domain tests/conftest.py tests/unit/domain && git commit -m "feat: define task domain and state machine"`

---

### Task 3: Transactional SQLite Repository

**Files:**
- Create: `src/testforge/persistence/__init__.py`
- Create: `src/testforge/persistence/schema.py`
- Create: `src/testforge/persistence/repository.py`
- Create: `tests/unit/persistence/test_repository.py`

**Interfaces:**
- Consumes: `TaskRecord`, `TaskState`, `MetricSnapshot`, and approval/audit value objects from Task 2.
- Produces: `SQLiteTaskRepository.create_task`, `get_task`, `record_transition`, `add_attempt`, `add_metric`, `add_audit_event`, and `list_task_events`.

The repository contracts are explicit and return `None` for successful writes:

```python
def add_attempt(self, task_id: UUID, proposal: TestProposal) -> None: ...
def add_metric(
    self,
    task_id: UUID,
    metric: MetricSnapshot,
    *,
    kind: Literal["baseline", "latest"],
) -> None: ...
def add_audit_event(self, event: AuditEvent) -> None: ...
def list_task_events(self, task_id: UUID) -> tuple[AuditEvent, ...]: ...
```

`add_attempt` appends an immutable proposal snapshot. `add_metric` appends an immutable metric snapshot and atomically updates the matching `TaskRecord.baseline_metrics` or `TaskRecord.latest_metrics` field; any other `kind` is rejected. `add_audit_event` appends the supplied immutable event. Every write validates that the task exists and rolls back completely on failure. Event listing is deterministic by `occurred_at` and then insertion order.

- [ ] **Step 1: Write the failing atomic-transition test**

```python
from testforge.domain.state_machine import TaskEvent, TaskState
from testforge.persistence.repository import SQLiteTaskRepository


def test_record_transition_updates_task_and_appends_event_atomically(tmp_path, sample_task):
    repo = SQLiteTaskRepository(tmp_path / "testforge.db")
    repo.create_task(sample_task)
    repo.record_transition(sample_task.id, TaskEvent.START, TaskState.VALIDATING_INPUT, reason="started")
    assert repo.get_task(sample_task.id).state is TaskState.VALIDATING_INPUT
    assert [event.reason for event in repo.list_task_events(sample_task.id)] == ["started"]
```

- [ ] **Step 2: Run repository test to verify RED**

Run: `python -m pytest tests/unit/persistence/test_repository.py::test_record_transition_updates_task_and_appends_event_atomically -v`  
Expected: FAIL because the repository does not exist.

- [ ] **Step 3: Implement schema and repository transaction**

```python
class SQLiteTaskRepository:
    def __init__(self, path: Path) -> None:
        self._engine = create_engine(f"sqlite+pysqlite:///{path}")
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)
        Base.metadata.create_all(self._engine)

    def create_task(self, task: TaskRecord) -> None:
        with self._session_factory.begin() as session:
            session.add(TaskRow(id=str(task.id), state=task.state.value, payload=task.model_dump(mode="json")))

    def get_task(self, task_id: UUID) -> TaskRecord:
        with self._session_factory() as session:
            row = session.get(TaskRow, str(task_id))
            if row is None:
                raise InputError(f"task {task_id} does not exist")
            return TaskRecord.model_validate({**row.payload, "state": row.state})

    def record_transition(self, task_id: UUID, event: TaskEvent, next_state: TaskState, reason: str) -> None:
        with self._session_factory.begin() as session:
            row = session.get(TaskRow, str(task_id))
            if row is None:
                raise InputError(f"task {task_id} does not exist")
            row.state = next_state.value
            self._insert_event(session, AuditEventRow(task_id=str(task_id), event=event.value, reason=reason))

    def _insert_event(self, session: Session, row: AuditEventRow) -> None:
        session.add(row)
```

Use JSON columns only for immutable snapshots; keep state, timestamps, foreign keys, patch hashes, and event types as explicit columns.

```python
class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    state: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(48), nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
```

- [ ] **Step 4: Add rollback and resume tests**

```python
def test_failed_event_insert_rolls_back_state(tmp_path, sample_task, monkeypatch):
    repo = SQLiteTaskRepository(tmp_path / "testforge.db")
    repo.create_task(sample_task)
    monkeypatch.setattr(repo, "_insert_event", lambda *args: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        repo.record_transition(sample_task.id, TaskEvent.INPUT_VALID, TaskState.VALIDATING_INPUT, "validated")
    assert repo.get_task(sample_task.id).state is TaskState.CREATED
```

Run: `python -m pytest tests/unit/persistence -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/persistence tests/unit/persistence && git commit -m "feat: persist task state and audit events"`

---

### Task 4: Deterministic Governance Policy

**Files:**
- Create: `src/testforge/governance/__init__.py`
- Create: `src/testforge/governance/policy.py`
- Create: `tests/unit/governance/test_policy.py`

**Interfaces:**
- Consumes: `ProjectConfig`, `TaskBudget`, `TestProposal`, `RefactorProposal`, `PolicyViolation`.
- Produces: `GovernancePolicy.validate_read`, `validate_test_proposal`, `validate_refactor_proposal`, and `validate_budget`.

- [ ] **Step 1: Write failing path-escape and source-write tests**

```python
def test_rejects_parent_directory_escape(policy):
    with pytest.raises(PolicyViolation, match="outside repository"):
        policy.validate_read("../secrets.txt")


def test_rejects_source_write_without_refactor_approval(policy):
    proposal = TestProposal(path="src/calculator.py", content="pass\n", strategy="make test pass")
    with pytest.raises(PolicyViolation, match="test directory"):
        policy.validate_test_proposal(proposal)
```

- [ ] **Step 2: Run policy tests to verify RED**

Run: `python -m pytest tests/unit/governance/test_policy.py -v`  
Expected: FAIL because `GovernancePolicy` does not exist.

- [ ] **Step 3: Implement canonical-path and patch-limit checks**

```python
class GovernancePolicy:
    def __init__(self, repository_root: Path, tests_root: Path, max_patch_bytes: int = 65536, max_patch_lines: int = 600):
        self.repository_root = repository_root.resolve()
        self.tests_root = tests_root
        self.max_patch_bytes = max_patch_bytes
        self.max_patch_lines = max_patch_lines

    def validate_read(self, relative_path: str) -> Path:
        candidate = (self.repository_root / relative_path).resolve(strict=False)
        if not candidate.is_relative_to(self.repository_root.resolve()):
            raise PolicyViolation("path is outside repository")
        return candidate

    def validate_test_proposal(self, proposal: TestProposal) -> Path:
        candidate = self.validate_read(proposal.path)
        if not candidate.is_relative_to((self.repository_root / self.tests_root).resolve()):
            raise PolicyViolation("candidate is outside configured test directory")
        if len(proposal.content.encode("utf-8")) > self.max_patch_bytes:
            raise PolicyViolation("candidate exceeds patch byte limit")
        return candidate
```

- [ ] **Step 4: Add symlink, deletion, unknown-action, and exhausted-budget cases**

Create a real symlink fixture when supported; skip only when the OS denies test symlink creation. Assert resolved symlink escape is rejected. Assert empty replacement of an existing file, undeclared action types, attempt 6, LLM call 7, and active second 2701 are rejected.

```python
def test_rejects_symlink_escape(policy, tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    link = policy.repository_root / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("test environment does not permit symlink creation")
    with pytest.raises(PolicyViolation, match="outside repository"):
        policy.validate_read("linked.txt")


def test_rejects_exhausted_default_budget(policy):
    usage = BudgetUsage(attempts=6, llm_calls=6, active_seconds=120, mutants=10)
    with pytest.raises(PolicyViolation, match="attempt budget"):
        policy.validate_budget(usage, TaskBudget())


def test_rejects_empty_replacement_of_existing_test(policy, existing_test):
    with pytest.raises(PolicyViolation, match="deletion"):
        policy.validate_test_proposal(TestProposal(path=str(existing_test.relative_to(policy.repository_root)), content="", strategy="delete"))
```

Run: `python -m pytest tests/unit/governance -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/governance tests/unit/governance && git commit -m "feat: enforce deterministic action policy"`

---

### Task 5: Hash-Bound Approvals and Atomic Write-Back

**Files:**
- Create: `src/testforge/governance/approval.py`
- Create: `src/testforge/governance/apply.py`
- Modify: `src/testforge/persistence/schema.py`
- Modify: `src/testforge/persistence/repository.py`
- Create: `tests/unit/governance/test_approval.py`
- Create: `tests/unit/governance/test_apply.py`

**Interfaces:**
- Consumes: validated proposals from Task 4 and repository events from Task 3.
- Produces: `sha256_text`, `ApprovalService.request`, `ApprovalService.decide`, and `AtomicPatchApplier.apply_file_replacement`.

- [ ] **Step 1: Write the failing changed-patch approval test**

```python
def test_approval_is_valid_only_for_exact_patch(approval_service):
    request = approval_service.request(kind="apply_tests", patch="original")
    approval_service.decide(request.id, approved=True, patch_hash=request.patch_hash, actor="owner")
    with pytest.raises(PolicyViolation, match="patch hash"):
        approval_service.require_approved(request.id, patch="changed")
```

- [ ] **Step 2: Run approval test to verify RED**

Run: `python -m pytest tests/unit/governance/test_approval.py -v`  
Expected: FAIL because approval support does not exist.

- [ ] **Step 3: Implement hash-bound decisions**

```python
def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ApprovalService:
    def request(self, kind: str, patch: str) -> ApprovalRequest:
        request = ApprovalRequest(kind=kind, patch_hash=sha256_text(patch), status=ApprovalStatus.PENDING)
        self.repository.create_approval(request)
        return request

    def decide(self, approval_id: UUID, approved: bool, patch_hash: str, actor: str) -> ApprovalRequest:
        request = self.repository.get_approval(approval_id)
        if request.patch_hash != patch_hash:
            raise PolicyViolation("decision patch hash does not match request")
        decided = request.model_copy(update={"status": ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED, "actor": actor, "decided_at": self.clock.now()})
        self.repository.update_approval(decided)
        return decided
    def require_approved(self, approval_id: UUID, patch: str) -> ApprovalRequest:
        request = self.repository.get_approval(approval_id)
        if request.status is not ApprovalStatus.APPROVED or request.patch_hash != sha256_text(patch):
            raise PolicyViolation("approval does not match patch hash")
        return request
```

- [ ] **Step 4: Write RED/GREEN tests for stale-safe atomic write-back**

```python
def test_apply_rejects_changed_destination(tmp_path, applier, approved_patch):
    target = tmp_path / "tests/test_math.py"
    target.parent.mkdir()
    target.write_text("user change\n", encoding="utf-8")
    with pytest.raises(StaleWorkspaceError):
        applier.apply_file_replacement(target, expected_hash=sha256_text("old\n"), new_content=approved_patch.content)
```

Implement write-back by writing a sibling temporary file, flushing it, and using `os.replace`; delete the temporary file on failure. Re-run: `python -m pytest tests/unit/governance -v`. Expected: PASS.

```python
class AtomicPatchApplier:
    def apply_file_replacement(self, target: Path, expected_hash: str, new_content: str) -> None:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if sha256_text(current) != expected_hash:
            raise StaleWorkspaceError("destination changed after validation")
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                handle.write(new_content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
```

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/governance src/testforge/persistence tests/unit/governance && git commit -m "feat: bind approvals to atomic patches"`

---

### Task 6: Provider-Neutral LLM Contract and Scripted Mock

**Files:**
- Create: `src/testforge/llm/__init__.py`
- Create: `src/testforge/llm/protocol.py`
- Create: `src/testforge/llm/mock.py`
- Create: `tests/unit/llm/test_mock.py`

**Interfaces:**
- Consumes: `TestProposal`, `RefactorProposal`, `FeedbackPacket` from Task 2.
- Produces: `GenerationContext`, `LLMClient` protocol, `LLMResponse`, and `MockLLMClient` with recorded calls.

- [ ] **Step 1: Write the failing scripted-response test**

```python
def test_mock_returns_script_in_order_and_records_feedback():
    first = LLMResponse(test=TestProposal(path="tests/test_calc.py", content="def test_one():\n    assert True\n", strategy="smoke"))
    second = LLMResponse(test=TestProposal(path="tests/test_calc.py", content="def test_one():\n    assert add(1, 1) == 2\n", strategy="strong assertion"))
    client = MockLLMClient([first, second])
    assert client.generate(context(), feedback=None) == first
    assert client.generate(context(), feedback=surviving_mutant_feedback()) == second
    assert client.calls[1].feedback.failure_category == "surviving_mutant"
```

- [ ] **Step 2: Run mock test to verify RED**

Run: `python -m pytest tests/unit/llm/test_mock.py -v`  
Expected: FAIL because LLM modules do not exist.

- [ ] **Step 3: Implement protocol and discriminated response schema**

```python
class LLMClient(Protocol):
    def generate(self, context: GenerationContext, feedback: FeedbackPacket | None) -> LLMResponse:
        raise NotImplementedError("LLM providers must return one validated action")


class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    test: TestProposal | None = None
    refactor: RefactorProposal | None = None

    @model_validator(mode="after")
    def exactly_one_action(self):
        if (self.test is None) == (self.refactor is None):
            raise ValueError("response must contain exactly one action")
        return self
```

- [ ] **Step 4: Implement exhausted-script and immutability cases**

`MockLLMClient.generate` pops no data; it advances an index, records immutable call snapshots, and raises `LLMError("mock script exhausted")` after the last response. Run `python -m pytest tests/unit/llm -v`. Expected: PASS.

```python
class MockLLMClient:
    def __init__(self, responses: Sequence[LLMResponse]) -> None:
        self.responses = tuple(responses)
        self.calls: list[LLMCall] = []
        self._index = 0

    def generate(self, context: GenerationContext, feedback: FeedbackPacket | None) -> LLMResponse:
        self.calls.append(LLMCall(context=context, feedback=feedback))
        if self._index >= len(self.responses):
            raise LLMError("mock script exhausted")
        response = self.responses[self._index]
        self._index += 1
        return response
```

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/llm tests/unit/llm && git commit -m "feat: add provider-neutral scripted LLM"`

---

### Task 7: Analyzer Result Models and Deterministic Parsers

**Files:**
- Create: `src/testforge/tools/__init__.py`
- Create: `src/testforge/tools/results.py`
- Create: `src/testforge/tools/parsers.py`
- Create: `tests/unit/tools/test_parsers.py`
- Create: `tests/fixtures/tool_output/pytest.json`
- Create: `tests/fixtures/tool_output/coverage.json`
- Create: `tests/fixtures/tool_output/mutmut.xml`

**Interfaces:**
- Consumes: `MetricSnapshot`, `ToolExecutionError`.
- Produces: `CommandResult`, `PytestResult`, `CoverageResult`, `MutationResult`, `parse_pytest_json`, `parse_coverage_json`, `parse_mutmut_junit`, and `metric_snapshot_from_results`.

- [ ] **Step 1: Write failing fixture parser tests**

```python
def test_parse_tools_into_one_metric_snapshot(fixture_text):
    pytest_result = parse_pytest_json(fixture_text("pytest.json"))
    coverage_result = parse_coverage_json(fixture_text("coverage.json"), target="src/calc.py")
    mutation_result = parse_mutmut_junit(fixture_text("mutmut.xml"))
    snapshot = metric_snapshot_from_results(pytest_result, coverage_result, mutation_result)
    assert (snapshot.tests_passed, snapshot.tests_failed, snapshot.tests_skipped) == (8, 0, 0)
    assert snapshot.branch_coverage == 75.0
    assert (snapshot.mutants_total, snapshot.mutants_killed, snapshot.mutants_survived) == (4, 3, 1)
```

- [ ] **Step 2: Run parser tests to verify RED**

Run: `python -m pytest tests/unit/tools/test_parsers.py -v`  
Expected: FAIL because result parsers do not exist.

- [ ] **Step 3: Implement strict parsers using documented JSON fields**

```python
def parse_coverage_json(raw: str, target: str) -> CoverageResult:
    try:
        payload = json.loads(raw)
        summary = payload["files"][target]["summary"]
        return CoverageResult(
            branch_percent=float(summary["percent_covered_display"]),
            missing_lines=tuple(payload["files"][target]["missing_lines"]),
            missing_branches=tuple(tuple(item) for item in payload["files"][target]["missing_branches"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ToolExecutionError("invalid coverage JSON") from exc
```

Apply the same strict approach to pytest and mutmut. Never infer success from free-form console prose.

```python
def parse_pytest_json(raw: str) -> PytestResult:
    try:
        summary = json.loads(raw)["summary"]
        return PytestResult(passed=int(summary.get("passed", 0)), failed=int(summary.get("failed", 0)), skipped=int(summary.get("skipped", 0)))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ToolExecutionError("invalid pytest JSON") from exc


def parse_mutmut_junit(raw: str) -> MutationResult:
    try:
        root = ElementTree.fromstring(raw)
        cases = root.findall(".//testcase")
        killed = sum(case.find("failure") is not None for case in cases)
        survived = sum(case.find("failure") is None and case.find("error") is None for case in cases)
        errors = sum(case.find("error") is not None for case in cases)
        return MutationResult(supported=True, total=len(cases), killed=killed, survived=survived, errors=errors)
    except ElementTree.ParseError as exc:
        raise ToolExecutionError("invalid mutmut JUnit XML") from exc


def metric_snapshot_from_results(pytest_result: PytestResult, coverage_result: CoverageResult, mutation_result: MutationResult) -> MetricSnapshot:
    return MetricSnapshot(
        tests_passed=pytest_result.passed,
        tests_failed=pytest_result.failed,
        tests_skipped=pytest_result.skipped,
        branch_coverage=coverage_result.branch_percent,
        mutants_total=mutation_result.total,
        mutants_killed=mutation_result.killed,
        mutants_survived=mutation_result.survived,
        mutation_status="supported" if mutation_result.supported else "unsupported",
    )
```

- [ ] **Step 4: Add malformed, timeout, unsupported-mutation, and redaction cases**

Assert malformed JSON raises `ToolExecutionError`; explicit `unsupported` produces `MutationResult(supported=False)`; timeout remains an error rather than unsupported; absolute workspace paths and values matching `sk-*` are redacted from diagnostic summaries.

Run: `python -m pytest tests/unit/tools -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/tools tests/unit/tools tests/fixtures/tool_output && git commit -m "feat: parse deterministic test feedback"`

---

### Task 8: Quality Gate and Feedback Classification

**Files:**
- Create: `src/testforge/feedback/__init__.py`
- Create: `src/testforge/feedback/quality_gate.py`
- Create: `src/testforge/feedback/engine.py`
- Create: `tests/unit/feedback/test_quality_gate.py`
- Create: `tests/unit/feedback/test_engine.py`

**Interfaces:**
- Consumes: `MetricSnapshot`, analyzer results, `QualityThreshold`, and attempt history.
- Produces: `QualityDecision`, `QualityGate.evaluate`, and `FeedbackEngine.build`.

- [ ] **Step 1: Write failing mutation-success and coverage-fallback tests**

```python
def test_mutation_gate_requires_new_kill_and_five_points(gate):
    baseline = metrics(branch=70, total=20, killed=10, survived=10)
    candidate = metrics(branch=70, total=20, killed=11, survived=9)
    assert gate.evaluate(baseline, candidate).passed is True


def test_timeout_does_not_activate_coverage_fallback(gate):
    baseline = metrics(branch=70, mutation_status="timeout")
    candidate = metrics(branch=80, mutation_status="timeout")
    decision = gate.evaluate(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "mutation_tool_error"
```

- [ ] **Step 2: Run quality tests to verify RED**

Run: `python -m pytest tests/unit/feedback/test_quality_gate.py -v`  
Expected: FAIL because `QualityGate` does not exist.

- [ ] **Step 3: Implement ordered quality checks**

```python
class QualityGate:
    def evaluate(self, baseline: MetricSnapshot, candidate: MetricSnapshot) -> QualityDecision:
        if candidate.tests_failed or candidate.tests_skipped > baseline.tests_skipped:
            return QualityDecision.failed("test_regression")
        if candidate.branch_coverage < baseline.branch_coverage or candidate.mutation_score < baseline.mutation_score:
            return QualityDecision.failed("metric_regression")
        if baseline.mutation_supported:
            killed_delta = candidate.mutants_killed - baseline.mutants_killed
            score_delta = candidate.mutation_score - baseline.mutation_score
            return QualityDecision(passed=killed_delta >= 1 and score_delta >= self.threshold.mutation_delta_points, reason="mutation_gate")
        if baseline.mutation_status == "unsupported":
            coverage_delta = candidate.branch_coverage - baseline.branch_coverage
            passed = coverage_delta >= self.threshold.coverage_delta_points or (baseline.branch_coverage < self.threshold.coverage_target_percent <= candidate.branch_coverage)
            return QualityDecision(passed=passed, reason="coverage_fallback")
        return QualityDecision.failed("mutation_tool_error")
```

- [ ] **Step 4: Write RED/GREEN feedback packet and stagnation tests**

```python
def test_surviving_mutant_feedback_names_mutant_and_changes_constraint(engine):
    packet = engine.build(baseline(), candidate_with_survivor("src/calc.py:12:+ -> -"), prior_attempts=[])
    assert packet.failure_category == "surviving_mutant"
    assert packet.surviving_mutants == ("src/calc.py:12:+ -> -",)
    assert "assertion" in packet.constraints_for_next_attempt[0]
```

Implement categories from SPEC §4.4 and mark `stagnated=True` after two consecutive attempts with identical coverage and mutation metrics. Run `python -m pytest tests/unit/feedback -v`. Expected: PASS.

```python
class FeedbackEngine:
    def build(self, baseline: MetricSnapshot, candidate: MetricSnapshot, prior_attempts: Sequence[AttemptSummary], surviving_mutants: tuple[str, ...] = ()) -> FeedbackPacket:
        if candidate.tests_failed:
            category = "test_failure"
            constraints = ("repair the failing assertion or fixture without changing production code",)
        elif surviving_mutants:
            category = "surviving_mutant"
            constraints = ("add an assertion that distinguishes the surviving mutant from the original behavior",)
        elif candidate.branch_coverage <= baseline.branch_coverage:
            category = "coverage_not_improved"
            constraints = ("exercise one listed uncovered branch with a deterministic input",)
        else:
            category = "quality_threshold_missed"
            constraints = ("strengthen assertions while preserving all passing tests",)
        recent = tuple((item.branch_coverage, item.mutation_score) for item in prior_attempts[-2:])
        stagnated = len(recent) == 2 and recent[0] == recent[1]
        return FeedbackPacket(failure_category=category, surviving_mutants=surviving_mutants, constraints_for_next_attempt=constraints, stagnated=stagnated)
```

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/feedback tests/unit/feedback && git commit -m "feat: drive generation with quality feedback"`

---

### Task 9: Structured Project Memory

**Files:**
- Create: `src/testforge/memory.py`
- Modify: `src/testforge/persistence/schema.py`
- Modify: `src/testforge/persistence/repository.py`
- Create: `tests/unit/test_memory.py`

**Interfaces:**
- Consumes: persisted `MemoryEntry` records and current target/failure tags.
- Produces: `ProjectMemory.remember`, `select`, `list_entries`, and `clear_project`.

- [ ] **Step 1: Write failing project-isolation and bounded-selection tests**

```python
def test_memory_selects_only_same_project_matching_tags(memory):
    memory.remember("project-a", kind="strategy", tags=("fixture",), summary="use monkeypatch")
    memory.remember("project-b", kind="strategy", tags=("fixture",), summary="foreign")
    assert [entry.summary for entry in memory.select("project-a", tags=("fixture",), limit=5)] == ["use monkeypatch"]


def test_memory_rejects_source_or_secret_shaped_content(memory):
    with pytest.raises(PolicyViolation):
        memory.remember("project-a", kind="strategy", tags=(), summary="sk-secret-value")
```

- [ ] **Step 2: Run memory tests to verify RED**

Run: `python -m pytest tests/unit/test_memory.py -v`  
Expected: FAIL because `ProjectMemory` does not exist.

- [ ] **Step 3: Implement deterministic tagged selection**

```python
class ProjectMemory:
    def remember(self, project_id: str, kind: str, tags: tuple[str, ...], summary: str, source_task_id: UUID | None = None, expires_at: datetime | None = None) -> MemoryEntry:
        if len(summary) > 2000 or SECRET_PATTERN.search(summary):
            raise PolicyViolation("memory summary is too large or contains secret-like content")
        entry = MemoryEntry(project_id=project_id, kind=kind, tags=tags, summary=summary, source_task_id=source_task_id, created_at=self.clock.now(), expires_at=expires_at, version=1)
        self.repository.add_memory(entry)
        self.repository.trim_memory(project_id=project_id, maximum=500)
        return entry
    def select(self, project_id: str, tags: tuple[str, ...], limit: int = 8) -> tuple[MemoryEntry, ...]:
        entries = self.repository.find_memory(project_id=project_id, active_at=self.clock.now())
        ranked = sorted(entries, key=lambda item: (len(set(tags) & set(item.tags)), item.created_at), reverse=True)
        return tuple(ranked[:limit])
```

Reject summaries over 2,000 characters, secret-like patterns, and payloads marked as complete source or complete prompt.

- [ ] **Step 4: Add expiry, version, clear, and capacity tests**

Assert expired records are excluded, newer versions supersede older entries with the same key, `clear_project` removes only that project, and at most 500 active entries remain after insertion.

```python
def test_expired_and_foreign_entries_are_not_selected(memory, clock):
    memory.remember("a", "strategy", ("fixture",), "expired", expires_at=clock.now() - timedelta(seconds=1))
    memory.remember("b", "strategy", ("fixture",), "foreign")
    memory.remember("a", "strategy", ("fixture",), "current")
    assert [entry.summary for entry in memory.select("a", ("fixture",), limit=8)] == ["current"]


def test_clear_is_project_scoped(memory):
    memory.remember("a", "strategy", (), "remove")
    memory.remember("b", "strategy", (), "keep")
    memory.clear_project("a")
    assert memory.list_entries("a") == ()
    assert [entry.summary for entry in memory.list_entries("b")] == ["keep"]
```

Run: `python -m pytest tests/unit/test_memory.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/memory.py src/testforge/persistence tests/unit/test_memory.py && git commit -m "feat: add bounded structured project memory"`

---

### Task 10: Project Runner Image and Restricted Docker Sandbox

**Files:**
- Create: `src/testforge/sandbox/__init__.py`
- Create: `src/testforge/sandbox/image_builder.py`
- Create: `src/testforge/sandbox/docker_runner.py`
- Create: `docker/project-runner.Dockerfile.template`
- Create: `docker/project-runner.dockerignore`
- Create: `tests/unit/sandbox/test_image_builder.py`
- Create: `tests/unit/sandbox/test_docker_runner.py`
- Create: `tests/integration/sandbox/test_real_container.py`
- Create: `tests/fixtures/projects/simple_math/src/simple_math.py`
- Create: `tests/fixtures/projects/simple_math/tests/test_existing.py`

**Interfaces:**
- Consumes: `TaskBudget`, `CommandResult`, `SandboxError`, a user-confirmed trusted project root, and its dependency files.
- Produces: `ProjectImageBuilder.fingerprint`, `build`, `DockerSandboxRunner.run(argv, workspace, timeout_seconds) -> CommandResult`, and `cleanup()`.

- [ ] **Step 1: Write the failing dependency-image fingerprint and final-image boundary tests**

```python
def test_dependency_fingerprint_changes_with_pyproject(tmp_path, image_builder):
    project = tmp_path / "project"
    project.mkdir()
    config = project / "pyproject.toml"
    config.write_text("[project]\nname='sample'\ndependencies=[]\n", encoding="utf-8")
    first = image_builder.fingerprint(project)
    config.write_text("[project]\nname='sample'\ndependencies=['attrs']\n", encoding="utf-8")
    assert image_builder.fingerprint(project) != first


def test_generated_final_stage_copies_venv_but_not_project_source(image_builder, tmp_path):
    dockerfile = image_builder.render_dockerfile(tmp_path)
    final_stage = dockerfile.split("FROM python:3.12-slim AS runtime", 1)[1]
    assert "COPY --from=builder /opt/venv /opt/venv" in final_stage
    assert "COPY ." not in final_stage
```

- [ ] **Step 2: Run image-builder tests to verify RED**

Run: `python -m pytest tests/unit/sandbox/test_image_builder.py -v`  
Expected: FAIL because `ProjectImageBuilder` does not exist.

- [ ] **Step 3: Implement a local-only multi-stage project image build**

```dockerfile
FROM python:3.12-slim AS builder
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY . /build
RUN python -m pip install --no-cache-dir pytest coverage mutmut .

FROM python:3.12-slim AS runtime
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONPATH=/workspace/src
RUN useradd --uid 65532 --no-create-home testforge
USER 65532:65532
WORKDIR /workspace
```

`ProjectImageBuilder.build` uses a tag `testforge-project:<dependency fingerprint>`, requires an explicit `trusted_project=True` argument from the application layer, records that the build may access package indexes and execute the project's build backend, and never pushes the image. Reject `.env`, `.git`, key files, and user-home content from the build context.

- [ ] **Step 4: Run image-builder tests to verify GREEN**

Run: `python -m pytest tests/unit/sandbox/test_image_builder.py -v`  
Expected: PASS.

- [ ] **Step 5: Write the failing Docker option test with a fake client**

```python
def test_container_is_non_root_offline_and_resource_limited(tmp_path, fake_docker_client):
    runner = DockerSandboxRunner(fake_docker_client, image="testforge-runner:py312")
    runner.run(("python", "-m", "pytest", "-q"), workspace=tmp_path, timeout_seconds=60)
    options = fake_docker_client.containers.last_run_options
    assert options["network_disabled"] is True
    assert options["user"] == "65532:65532"
    assert options["mem_limit"] == "512m"
    assert options["nano_cpus"] == 1_000_000_000
    assert options["pids_limit"] == 128
    assert "/var/run/docker.sock" not in repr(options["volumes"])
```

- [ ] **Step 6: Run sandbox unit test to verify RED**

Run: `python -m pytest tests/unit/sandbox/test_docker_runner.py -v`  
Expected: FAIL because the sandbox runner does not exist.

- [ ] **Step 7: Implement container lifecycle and timeout cleanup**

```python
class DockerSandboxRunner:
    def __init__(self, client: DockerClient, image: str) -> None:
        self.client = client
        self.image = image

    def run(self, argv: tuple[str, ...], workspace: Path, timeout_seconds: int) -> CommandResult:
        tests_dir = workspace / "tests"
        container = self.client.containers.run(
            self.image,
            list(argv),
            detach=True,
            working_dir="/workspace",
            user="65532:65532",
            network_disabled=True,
            read_only=True,
            mem_limit="512m",
            nano_cpus=1_000_000_000,
            pids_limit=128,
            security_opt=["no-new-privileges:true"],
            cap_drop=["ALL"],
            volumes={
                str(workspace): {"bind": "/workspace", "mode": "ro"},
                str(tests_dir): {"bind": "/workspace/tests", "mode": "rw"},
            },
            tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
        )
        try:
            result = container.wait(timeout=timeout_seconds)
            return CommandResult(exit_code=int(result["StatusCode"]), stdout=container.logs(stdout=True, stderr=False).decode(), stderr=container.logs(stdout=False, stderr=True).decode())
        except Exception as exc:
            container.kill()
            raise SandboxError("sandbox command timed out or failed") from exc
        finally:
            container.remove(force=True)
```

- [ ] **Step 8: Add timeout/cleanup unit cases and a tagged real-container integration test**

```python
@pytest.mark.docker
def test_real_container_can_write_tests_but_not_source(built_fixture_image, fixture_workspace):
    runner = DockerSandboxRunner(docker.from_env(), image=built_fixture_image)
    tests = runner.run(("python", "-c", "open('/workspace/tests/generated.txt','w').write('ok')"), fixture_workspace, 30)
    source = runner.run(("python", "-c", "open('/workspace/src/forbidden.txt','w').write('no')"), fixture_workspace, 30)
    assert tests.exit_code == 0
    assert source.exit_code != 0
```

Build the fixture image with `ProjectImageBuilder`, assert `python -m pytest -q` exits 0, and skip only when the Docker daemon is unavailable.

Run: `python -m pytest tests/unit/sandbox -v`  
Expected: PASS.  
Run: `python -m pytest tests/integration/sandbox -m docker -v`  
Expected when Docker is available: PASS.

- [ ] **Step 9: Commit**

Commit: `git add src/testforge/sandbox docker tests/unit/sandbox tests/integration/sandbox tests/fixtures/projects/simple_math && git commit -m "feat: build and isolate project test environments"`

---

### Task 11: Domain-Only Tool Dispatcher

**Files:**
- Create: `src/testforge/tools/dispatcher.py`
- Create: `tests/unit/tools/test_dispatcher.py`

**Interfaces:**
- Consumes: `GovernancePolicy`, `DockerSandboxRunner`, parser functions, and proposal/result models.
- Produces: `ToolName`, validated `ToolRequest` models, and `DomainToolDispatcher.dispatch(request) -> ToolResult`.

- [ ] **Step 1: Write failing unknown-tool and valid-pytest dispatch tests**

```python
def test_unknown_tool_is_rejected(dispatcher):
    with pytest.raises(PolicyViolation, match="unknown domain tool"):
        dispatcher.dispatch_raw({"tool": "shell", "command": "rm -rf /"})


def test_run_pytest_uses_fixed_argv(dispatcher, sandbox):
    dispatcher.dispatch(RunPytestRequest())
    assert sandbox.last_argv == ("python", "-m", "pytest", "--json-report", "--json-report-file=/tmp/pytest.json", "-q")
```

- [ ] **Step 2: Run dispatcher tests to verify RED**

Run: `python -m pytest tests/unit/tools/test_dispatcher.py -v`  
Expected: FAIL because the dispatcher does not exist.

- [ ] **Step 3: Implement discriminated requests and explicit registry**

```python
class ToolName(StrEnum):
    READ_SOURCE = "read_source"
    READ_TESTS = "read_tests"
    WRITE_TEST = "write_test"
    RUN_PYTEST = "run_pytest"
    MEASURE_COVERAGE = "measure_coverage"
    RUN_MUTATION = "run_mutation"
    REQUEST_REFACTOR_APPROVAL = "request_refactor_approval"
    APPLY_APPROVED_REFACTOR = "apply_approved_refactor"
    EXPORT_PATCH = "export_patch"


class DomainToolDispatcher:
    def dispatch(self, request: ToolRequest) -> ToolResult:
        handler = self._handlers.get(request.tool)
        if handler is None:
            raise PolicyViolation("unknown domain tool")
        return handler(request)

    def dispatch_raw(self, payload: dict[str, object]) -> ToolResult:
        try:
            request = TOOL_REQUEST_ADAPTER.validate_python(payload)
        except ValidationError as exc:
            raise PolicyViolation("unknown domain tool or invalid parameters") from exc
        return self.dispatch(request)
```

Hard-code analyzer argument vectors in handlers. Never concatenate user strings into a command.

- [ ] **Step 4: Add read/write/refactor/export policy tests**

Assert every handler invokes the corresponding `GovernancePolicy` check, never returns complete source in an audit event, and refuses a refactor application without a matching approval ID and patch hash.

```python
def test_refactor_dispatch_requires_matching_approval(dispatcher, approval_service, refactor_request):
    approval = approval_service.request("refactor", refactor_request.patch)
    with pytest.raises(PolicyViolation, match="approval"):
        dispatcher.dispatch(ApplyApprovedRefactorRequest(proposal=refactor_request, approval_id=approval.id))


def test_audit_result_contains_hash_not_complete_source(dispatcher, source_request):
    result = dispatcher.dispatch(source_request)
    assert result.content_hash
    assert result.content not in result.audit_summary
```

Run: `python -m pytest tests/unit/tools -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/tools/dispatcher.py tests/unit/tools/test_dispatcher.py && git commit -m "feat: dispatch allowlisted test tools"`

---

### Task 12: Persisted Agent Engine and Mock-LLM Feedback Loop

**Files:**
- Create: `src/testforge/context.py`
- Create: `src/testforge/engine.py`
- Create: `src/testforge/application.py`
- Create: `tests/unit/test_engine.py`
- Create: `tests/integration/test_mock_loop.py`

**Interfaces:**
- Consumes: repository, state machine, LLM, dispatcher, feedback, quality gate, memory, governance, and approvals.
- Produces: `ContextBuilder.build`, `AgentEngine.advance(task_id)`, `run_until_blocked(task_id)`, `resume(task_id, approval_id)`, `ApplicationService` use cases, and `build_application` composition root.

- [ ] **Step 1: Write the failing one-transition-per-advance test**

```python
def test_advance_is_persisted_and_idempotent(engine, repo, created_task):
    result = engine.advance(created_task.id)
    assert result.previous_state is TaskState.CREATED
    assert result.current_state is TaskState.VALIDATING_INPUT
    assert repo.get_task(created_task.id).state is TaskState.VALIDATING_INPUT
    assert len(repo.list_task_events(created_task.id)) == 1
```

- [ ] **Step 2: Run engine unit test to verify RED**

Run: `python -m pytest tests/unit/test_engine.py -v`  
Expected: FAIL because `AgentEngine` does not exist.

- [ ] **Step 3: Implement explicit state handlers**

```python
class AgentEngine:
    def advance(self, task_id: UUID) -> TransitionResult:
        task = self.repository.get_task(task_id)
        handler = self._handlers.get(task.state)
        if handler is None:
            return TransitionResult(task.state, task.state, blocked=True, reason="terminal_or_waiting")
        event, reason = handler(task)
        next_state = transition(task.state, event)
        self.repository.record_transition(task.id, event, next_state, reason)
        return TransitionResult(task.state, next_state, blocked=next_state in BLOCKING_STATES, reason=reason)

    def run_until_blocked(self, task_id: UUID) -> TaskRecord:
        while True:
            result = self.advance(task_id)
            if result.blocked or result.current_state in TERMINAL_STATES:
                return self.repository.get_task(task_id)

    def resume(self, task_id: UUID, approval_id: UUID) -> TransitionResult:
        task = self.repository.get_task(task_id)
        if task.state not in {TaskState.AWAITING_REFACTOR_APPROVAL, TaskState.AWAITING_APPLY_APPROVAL}:
            raise InvalidTransition(state=task.state, event=TaskEvent.APPROVED)
        approval = self.approvals.require_approved(approval_id, task.pending_patch)
        next_state = transition(task.state, TaskEvent.APPROVED)
        self.repository.record_transition(task.id, TaskEvent.APPROVED, next_state, reason=f"approval:{approval.id}")
        return TransitionResult(previous_state=task.state, current_state=next_state, blocked=False, reason="approved")
```

Handlers must perform one externally visible action at most and persist its immutable result before the transition.

```python
BLOCKING_STATES = {TaskState.AWAITING_REFACTOR_APPROVAL, TaskState.AWAITING_APPLY_APPROVAL}
TERMINAL_STATES = {TaskState.COMPLETED, TaskState.NO_ACTION_NEEDED, TaskState.STOPPED, TaskState.FAILED, TaskState.CANCELLED, TaskState.STALE}


def _handle_generating(self, task: TaskRecord) -> tuple[TaskEvent, str]:
    self.policy.validate_budget(task.usage, task.budget)
    feedback = self.repository.latest_feedback(task.id)
    memory = self.memory.select(task.project_id, task.memory_tags)
    context = self.context_builder.build(task, memory)
    response = self.llm.generate(context, feedback)
    if response.refactor is not None:
        self.policy.validate_refactor_proposal(response.refactor)
        self.approvals.request("refactor", response.refactor.patch)
        return TaskEvent.REFACTOR_REQUESTED, "refactor proposal requires approval"
    if response.test is None:
        raise LLMError("validated response contains no test proposal")
    self.policy.validate_test_proposal(response.test)
    self.repository.add_attempt(task.id, response.test)
    return TaskEvent.PROPOSAL_READY, "test proposal validated"


def _handle_evaluating(self, task: TaskRecord) -> tuple[TaskEvent, str]:
    decision = self.quality_gate.evaluate(task.baseline_metrics, task.latest_metrics)
    if decision.passed:
        self.approvals.request("apply_tests", task.pending_patch)
        return TaskEvent.QUALITY_PASSED, decision.reason
    feedback = self.feedback.build(task.baseline_metrics, task.latest_metrics, task.attempt_summaries, task.surviving_mutants)
    self.repository.add_feedback(task.id, feedback)
    if feedback.stagnated or task.usage.exhausted(task.budget):
        return TaskEvent.BUDGET_EXHAUSTED, "feedback loop stopped by stagnation or budget"
    return TaskEvent.QUALITY_MISSED, decision.reason


class ContextBuilder:
    def build(self, task: TaskRecord, memory: Sequence[MemoryEntry]) -> GenerationContext:
        source = self.dispatcher.dispatch(ReadSourceRequest(path=task.target_module))
        tests = self.dispatcher.dispatch(ReadTestsRequest(target_module=task.target_module))
        return GenerationContext(
            target_module=task.target_module,
            source=source.content,
            existing_tests=tests.content,
            baseline=task.baseline_metrics,
            constraints=task.constraints,
            memory=tuple(entry.summary for entry in memory[:8]),
        )
```

- [ ] **Step 4: Write the failing full mock-loop mechanism test**

```python
def test_surviving_mutant_feedback_changes_second_llm_action(mock_loop):
    task = mock_loop.run()
    assert task.state is TaskState.AWAITING_APPLY_APPROVAL
    assert mock_loop.llm.calls[0].feedback is None
    assert mock_loop.llm.calls[1].feedback.failure_category == "surviving_mutant"
    assert mock_loop.llm.responses[0].test.strategy == "weak assertion"
    assert mock_loop.llm.responses[1].test.strategy == "kill arithmetic mutant"
    assert mock_loop.metrics[-1].mutation_score - mock_loop.metrics[0].mutation_score >= 5.0
```

Build the fixture with scripted analyzer results: baseline has one surviving mutant, attempt one leaves it alive, attempt two kills it. Add tests for `NO_ACTION_NEEDED`, two-round stagnation, budget exhaustion, refactor pause/resume, apply pause, cancellation, and stale workspace.

- [ ] **Step 5: Run complete engine tests and commit**

Run: `python -m pytest tests/unit/test_engine.py tests/integration/test_mock_loop.py -v`  
Expected: PASS.  
Commit: `git add src/testforge/context.py src/testforge/engine.py src/testforge/application.py tests/unit/test_engine.py tests/integration/test_mock_loop.py && git commit -m "feat: run persisted feedback-driven agent loop"`

---

### Task 13: Secure Credential Store

**Files:**
- Create: `src/testforge/credentials.py`
- Create: `tests/unit/test_credentials.py`

**Interfaces:**
- Consumes: OS keyring backend and optional environment mapping.
- Produces: `CredentialStore.set`, `status`, `get`, `clear`, and `CredentialStatus`.

- [ ] **Step 1: Write failing no-plaintext-status and keyring tests**

```python
def test_status_never_returns_secret(fake_keyring):
    store = CredentialStore(fake_keyring, service_name="testforge")
    store.set("openai", "sk-example-not-real")
    status = store.status("openai")
    assert status.configured is True
    assert "sk-example" not in repr(status)
    assert fake_keyring.saved == ("testforge", "openai", "sk-example-not-real")
```

- [ ] **Step 2: Run credential tests to verify RED**

Run: `python -m pytest tests/unit/test_credentials.py -v`  
Expected: FAIL because `CredentialStore` does not exist.

- [ ] **Step 3: Implement keyring-first storage and explicit dotenv fallback**

```python
class CredentialStore:
    def __init__(self, backend: KeyringBackend, service_name: str, environment: Mapping[str, str] | None = None) -> None:
        self.backend = backend
        self.service_name = service_name
        self.environment = dict(environment or {})

    def set(self, provider: str, secret: str) -> None:
        if not secret.strip():
            raise CredentialError("credential cannot be empty")
        self.backend.set_password(self.service_name, provider, secret)

    def status(self, provider: str) -> CredentialStatus:
        configured = self.backend.get_password(self.service_name, provider) is not None
        return CredentialStatus(provider=provider, configured=configured, source="keyring" if configured else None)

    def get(self, provider: str, allow_dotenv: bool = False) -> str:
        secret = self.backend.get_password(self.service_name, provider)
        if secret is None and allow_dotenv:
            secret = self.environment.get("OPENAI_API_KEY")
        if secret is None:
            raise CredentialError(f"credential for {provider} is not configured")
        return secret

    def clear(self, provider: str) -> None:
        try:
            self.backend.delete_password(self.service_name, provider)
        except keyring.errors.PasswordDeleteError:
            return
```

- [ ] **Step 4: Add clear, missing-key, explicit-fallback, and redaction tests**

Assert environment values are ignored unless `allow_dotenv=True`; exception and status representations contain no secret; clear is idempotent when the backend reports a missing entry.

```python
def test_dotenv_is_ignored_without_explicit_opt_in(fake_keyring):
    store = CredentialStore(fake_keyring, "testforge", environment={"OPENAI_API_KEY": "sk-not-real"})
    with pytest.raises(CredentialError):
        store.get("openai", allow_dotenv=False)


def test_clear_missing_credential_is_idempotent(fake_keyring):
    store = CredentialStore(fake_keyring, "testforge")
    store.clear("openai")
    store.clear("openai")
    assert store.status("openai").configured is False
```

Run: `python -m pytest tests/unit/test_credentials.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/credentials.py tests/unit/test_credentials.py && git commit -m "feat: manage API keys with OS keyring"`

---

### Task 14: OpenAI LLM Adapter

**Files:**
- Create: `src/testforge/llm/openai_adapter.py`
- Create: `tests/unit/llm/test_openai_adapter.py`

**Interfaces:**
- Consumes: `LLMClient`, `GenerationContext`, `FeedbackPacket`, `LLMResponse`, and `CredentialStore`.
- Produces: `OpenAIClient.generate` with normalized `LLMError` failures.

- [ ] **Step 1: Write the failing structured-response adapter test**

```python
def test_openai_adapter_requests_validated_llm_response(fake_openai, credential_store):
    adapter = OpenAIClient(lambda api_key: fake_openai, credential_store, model="configured-model")
    response = adapter.generate(context(), feedback=None)
    assert response.test.path == "tests/test_calc.py"
    call = fake_openai.responses.parse_calls[0]
    assert call["model"] == "configured-model"
    assert call["text_format"] is LLMResponse
    assert "shell" not in call["input"]
```

- [ ] **Step 2: Run adapter test to verify RED**

Run: `python -m pytest tests/unit/llm/test_openai_adapter.py -v`  
Expected: FAIL because the OpenAI adapter does not exist.

- [ ] **Step 3: Implement Responses API structured parsing behind the provider-neutral interface**

```python
class OpenAIClient:
    def generate(self, context: GenerationContext, feedback: FeedbackPacket | None) -> LLMResponse:
        api_key = self.credentials.get("openai")
        client = self.client_factory(api_key=api_key)
        try:
            parsed = client.responses.parse(
                model=self.model,
                input=self._build_input(context, feedback),
                text_format=LLMResponse,
            )
            if parsed.output_parsed is None:
                raise LLMError("provider returned no structured action")
            return parsed.output_parsed
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(self._safe_error_category(exc)) from exc
```

`_build_input` includes target summaries, constraints, selected memory, baseline, and feedback but no key, full repository, or arbitrary tool descriptions.

- [ ] **Step 4: Add authentication, rate-limit, timeout, refusal, invalid-schema, and secret-redaction tests**

Use fake SDK exceptions; assert each becomes one of `authentication`, `rate_limit`, `timeout`, `refusal`, or `invalid_response` without provider message text that could contain a credential.

```python
@pytest.mark.parametrize(
    "provider_error,category",
    [(FakeAuthenticationError(), "authentication"), (FakeRateLimitError(), "rate_limit"), (FakeTimeoutError(), "timeout")],
)
def test_provider_errors_are_normalized_without_message(fake_openai, credential_store, provider_error, category):
    fake_openai.responses.raise_on_parse = provider_error
    adapter = OpenAIClient(lambda api_key: fake_openai, credential_store, model="configured-model")
    with pytest.raises(LLMError, match=category) as captured:
        adapter.generate(context(), feedback=None)
    assert "sk-" not in str(captured.value)
```

Run: `python -m pytest tests/unit/llm -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/llm/openai_adapter.py tests/unit/llm/test_openai_adapter.py && git commit -m "feat: add OpenAI structured-output adapter"`

---

### Task 15: Typer CLI and Application Commands

**Files:**
- Create: `src/testforge/cli.py`
- Create: `tests/unit/test_cli.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `ApplicationService` and `CredentialStore`.
- Produces: `testforge init`, `credentials set|status|clear`, `run`, `status`, `approve`, `reject`, `apply`, `history`, and `serve` commands.

- [ ] **Step 1: Write failing init/run/status CLI tests**

```python
def test_run_prints_task_id_without_secret(cli_runner, app, monkeypatch):
    monkeypatch.setattr("testforge.cli.get_application", lambda: app)
    result = cli_runner.invoke(cli, ["run", "src/calc.py"])
    assert result.exit_code == 0
    assert str(app.created_task.id) in result.stdout
    assert "sk-" not in result.stdout


def test_init_requires_explicit_trust_before_dependency_build(cli_runner, app, monkeypatch):
    monkeypatch.setattr("testforge.cli.get_application", lambda: app)
    result = cli_runner.invoke(cli, ["init", "."], input="n\n")
    assert result.exit_code == 1
    assert app.project_image_builds == []
```

- [ ] **Step 2: Run CLI tests to verify RED**

Run: `python -m pytest tests/unit/test_cli.py -v`  
Expected: FAIL because CLI does not exist.

- [ ] **Step 3: Implement commands as thin application-service calls**

```python
cli = typer.Typer(no_args_is_help=True)
credentials_cli = typer.Typer()
cli.add_typer(credentials_cli, name="credentials")


@cli.command()
def init(repository: Path = Path(".")) -> None:
    trusted = typer.confirm("This build may download dependencies and execute the project's build backend. Trust this repository?")
    if not trusted:
        raise typer.Exit(code=1)
    project = get_application().initialize_project(repository, trusted_project=True)
    typer.echo(f"initialized {project.id} with sandbox image {project.sandbox_image}")


@cli.command()
def run(target_module: str) -> None:
    task = get_application().create_and_start(target_module)
    typer.echo(str(task.id))


@credentials_cli.command("set")
def credential_set(provider: str = "openai") -> None:
    secret = typer.prompt("API key", hide_input=True, confirmation_prompt=True)
    get_credentials().set(provider, secret)
    typer.echo(f"{provider} credential configured")
```

Add `[project.scripts] testforge = "testforge.cli:cli"` to `pyproject.toml`.

- [ ] **Step 4: Add approval, stale, cancellation, history, and credential-output tests**

Assert approval commands require UUIDs, show patch hashes but not full source, rejected approvals resume correctly, and `credentials status` prints configured/source only.

```python
def test_credentials_status_shows_no_value(cli_runner, configured_credentials, monkeypatch):
    monkeypatch.setattr("testforge.cli.get_credentials", lambda: configured_credentials)
    result = cli_runner.invoke(cli, ["credentials", "status", "--provider", "openai"])
    assert result.exit_code == 0
    assert "configured" in result.stdout
    assert "sk-" not in result.stdout


def test_reject_requires_valid_approval_uuid(cli_runner):
    result = cli_runner.invoke(cli, ["reject", "not-a-uuid"])
    assert result.exit_code != 0
```

Run: `python -m pytest tests/unit/test_cli.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/cli.py tests/unit/test_cli.py pyproject.toml && git commit -m "feat: expose TestForge CLI workflows"`

---

### Task 16: Local FastAPI WebUI

**Files:**
- Create: `src/testforge/web/__init__.py`
- Create: `src/testforge/web/app.py`
- Create: `src/testforge/web/templates/base.html`
- Create: `src/testforge/web/templates/new_task.html`
- Create: `src/testforge/web/templates/task_detail.html`
- Create: `src/testforge/web/templates/approvals.html`
- Create: `src/testforge/web/static/htmx.min.js`
- Create: `src/testforge/web/static/HTMX-LICENSE.txt`
- Create: `tests/unit/web/test_routes.py`

**Interfaces:**
- Consumes: `ApplicationService` DTOs only.
- Produces: HTML routes for task creation, task detail, approval decisions, settings status, and memory clearing.

- [ ] **Step 1: Write failing route-boundary tests**

```python
def test_task_detail_shows_metrics_and_never_secret(test_client, fake_app):
    response = test_client.get(f"/tasks/{fake_app.task.id}")
    assert response.status_code == 200
    assert "Mutation score" in response.text
    assert "Awaiting approval" in response.text
    assert "sk-example" not in response.text
```

- [ ] **Step 2: Run Web route tests to verify RED**

Run: `python -m pytest tests/unit/web/test_routes.py -v`  
Expected: FAIL because Web app does not exist.

- [ ] **Step 3: Implement app factory and server-rendered routes**

```python
def create_app(application: ApplicationService, demo_mode: bool = False) -> FastAPI:
    app = FastAPI(title="TestForge")
    app.add_middleware(SessionMiddleware, secret_key=application.web_session_secret)
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

    @app.get("/tasks/{task_id}", response_class=HTMLResponse)
    def task_detail(request: Request, task_id: UUID) -> HTMLResponse:
        view = application.get_task_view(task_id)
        return templates.TemplateResponse(request, "task_detail.html", {"task": view, "demo_mode": demo_mode})

    @app.post("/approvals/{approval_id}/{decision}")
    def decide(approval_id: UUID, decision: Literal["approve", "reject"]) -> RedirectResponse:
        application.decide_approval(approval_id, approved=decision == "approve", actor="local-owner")
        return RedirectResponse(url="/approvals", status_code=303)

    return app
```

- [ ] **Step 4: Add CSRF token, invalid UUID, stale approval, memory-clear, accessibility, and local-static tests**

Assert every mutation form requires a session CSRF token; templates have labels, headings, keyboard-focus styles, textual state indicators, and no color-only meaning; HTMX is served locally with its license.

```python
def test_approval_rejects_missing_csrf(test_client, pending_approval):
    response = test_client.post(f"/approvals/{pending_approval.id}/approve")
    assert response.status_code == 403


def test_task_page_uses_local_htmx_and_accessible_status(test_client, fake_app):
    response = test_client.get(f"/tasks/{fake_app.task.id}")
    assert 'src="/static/htmx.min.js"' in response.text
    assert 'aria-live="polite"' in response.text
    assert "Awaiting approval" in response.text
```

Run: `python -m pytest tests/unit/web -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/web tests/unit/web && git commit -m "feat: add local task and approval WebUI"`

---

### Task 17: Public Mock Demo Mode

**Files:**
- Create: `src/testforge/demo.py`
- Create: `tests/fixtures/demo/weak_then_strong.json`
- Create: `tests/fixtures/demo/refactor_blocked.json`
- Create: `tests/unit/web/test_demo_mode.py`
- Create: `tests/e2e/test_demo_flow.py`

**Interfaces:**
- Consumes: `MockLLMClient`, fixture analyzer results, Web app factory.
- Produces: `DemoScenario`, `DemoApplicationFactory`, and demo-only routes that cannot accept external code or credentials.

- [ ] **Step 1: Write failing demo boundary test**

```python
def test_demo_mode_rejects_repository_upload_url_and_credentials(demo_client):
    response = demo_client.post("/demo/tasks", json={"repository_url": "https://example.com/repo.git", "api_key": "sk-not-real"})
    assert response.status_code == 422
    assert "repository_url" in response.text
    assert "api_key" in response.text
```

- [ ] **Step 2: Run demo tests to verify RED**

Run: `python -m pytest tests/unit/web/test_demo_mode.py -v`  
Expected: FAIL because demo mode does not exist.

- [ ] **Step 3: Implement closed fixture registry and demo factory**

```python
class DemoTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal["weak-then-strong", "refactor-blocked"]


class DisabledCredentialStore:
    def get(self, provider: str, allow_dotenv: bool = False) -> str:
        raise CredentialError("credentials are disabled in public demo mode")


class FixtureToolDispatcher:
    def __init__(self, results: Sequence[ToolResult]) -> None:
        self._results = iter(results)

    def dispatch(self, request: ToolRequest) -> ToolResult:
        try:
            return next(self._results)
        except StopIteration as exc:
            raise ToolExecutionError("demo tool script exhausted") from exc


class DemoApplicationFactory:
    def create(self, scenario: DemoTaskRequest) -> ApplicationService:
        fixture = self.registry[scenario.scenario]
        return build_application(
            llm=MockLLMClient(fixture.responses),
            dispatcher=FixtureToolDispatcher(fixture.tool_results),
            credentials=DisabledCredentialStore(),
            repository=SQLiteTaskRepository(Path(":memory:")),
        )
```

The request schema contains only `scenario`; FastAPI must reject every extra field.

- [ ] **Step 4: Add end-to-end weak-test → feedback → strong-test → approval test**

Use `TestClient` to select `weak-then-strong`, advance the task, assert the timeline contains one surviving-mutant feedback event, approve the final test diff, and assert the demo records a simulated write-back without touching disk.

```python
def test_weak_then_strong_demo_reaches_apply_approval_without_disk_write(demo_client, tmp_path):
    created = demo_client.post("/demo/tasks", json={"scenario": "weak-then-strong"})
    task_id = created.json()["task_id"]
    finished = demo_client.post(f"/demo/tasks/{task_id}/advance")
    assert finished.json()["state"] == "awaiting_apply_approval"
    detail = demo_client.get(f"/demo/tasks/{task_id}").json()
    assert [attempt["strategy"] for attempt in detail["attempts"]] == ["weak assertion", "kill arithmetic mutant"]
    assert detail["feedback"][0]["failure_category"] == "surviving_mutant"
    assert list(tmp_path.iterdir()) == []
```

Run: `python -m pytest tests/unit/web/test_demo_mode.py tests/e2e/test_demo_flow.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add src/testforge/demo.py tests/fixtures/demo tests/unit/web/test_demo_mode.py tests/e2e/test_demo_flow.py && git commit -m "feat: add closed public mock demonstration"`

---

### Task 18: Required Deterministic Mechanism Demonstration

**Files:**
- Create: `scripts/mechanism_demo.py`
- Create: `tests/e2e/test_mechanism_demo.py`

**Interfaces:**
- Consumes: `DemoApplicationFactory`, `GovernancePolicy`, and mock-loop fixtures.
- Produces: a network-free executable demonstration with stable JSON output.

- [ ] **Step 1: Write the failing demonstration contract test**

```python
def test_demo_reports_all_required_mechanisms(run_demo):
    report = run_demo()
    assert report["dangerous_action"]["blocked"] is True
    assert report["feedback_loop"]["first_strategy"] == "weak assertion"
    assert report["feedback_loop"]["second_strategy"] == "kill arithmetic mutant"
    assert report["quality_gate"]["passed"] is True
    assert report["final_state"] == "awaiting_apply_approval"
```

- [ ] **Step 2: Run the contract test to verify RED**

Run: `python -m pytest tests/e2e/test_mechanism_demo.py -v`  
Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement deterministic JSON report generation**

```python
def main() -> int:
    report = run_mechanism_demo()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["quality_gate"]["passed"] and report["dangerous_action"]["blocked"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

`run_mechanism_demo` first submits `src/calc.py` as a test proposal and captures the deterministic policy rejection; it then runs the scripted two-attempt loop and returns both strategies, feedback category, metric deltas, and final waiting-approval state.

- [ ] **Step 4: Verify network independence and stable output**

Run twice with an environment mapping that removes `OPENAI_API_KEY`; assert byte-identical JSON and no outbound client factory call.

```python
def test_demo_is_byte_stable_and_offline(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network used")))
    assert main() == 0
    first = capsys.readouterr().out
    assert main() == 0
    second = capsys.readouterr().out
    assert first == second
```

Run: `python scripts/mechanism_demo.py`  
Expected: exit 0 and one JSON document containing `dangerous_action`, `feedback_loop`, `quality_gate`, and `final_state`.  
Run: `python -m pytest tests/e2e/test_mechanism_demo.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

Commit: `git add scripts/mechanism_demo.py tests/e2e/test_mechanism_demo.py && git commit -m "test: demonstrate deterministic harness mechanisms"`

---

### Task 19: Distribution, CI, README, and Final Verification

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `.github/workflows/ci.yml`
- Create: `.gitlab-ci.yml`
- Create: `README.md`
- Create: `LICENSES.md`
- Create: `tests/e2e/test_distribution.py`
- Modify: `pyproject.toml`
- Modify: `AGENT_LOG.md`
- Modify: `PLAN.md`

**Interfaces:**
- Consumes: all completed application and test entry points.
- Produces: PyPI artifact, Docker image, platform-compatible CI, one-command test entry, and complete user/security documentation.

- [ ] **Step 1: Write failing packaging and container smoke tests**

```python
def test_installed_package_exposes_cli():
    result = subprocess.run([sys.executable, "-m", "testforge.cli", "--help"], text=True, capture_output=True, check=False)
    assert result.returncode == 0
    assert "TestForge" in result.stdout


def test_demo_health_endpoint(test_client):
    response = test_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "demo"}
```

- [ ] **Step 2: Run packaging smoke tests to verify RED**

Run: `python -m pytest tests/e2e/test_distribution.py -v`  
Expected: FAIL until the module entry point and health route are configured.

- [ ] **Step 3: Add reproducible package, Docker, and test commands**

```dockerfile
FROM python:3.12-slim AS runtime
RUN useradd --uid 10001 --create-home testforge
WORKDIR /app
COPY pyproject.toml README.md /app/
COPY src /app/src
RUN python -m pip install --no-cache-dir .
USER 10001
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "testforge.web.app:create_demo_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

Add `testforge-demo = "testforge.demo:main"` and include templates/static assets in the wheel. Define `python -m pytest` as the one-command test entry in README.

- [ ] **Step 4: Add dual CI with an exact `unit-test` job**

GitHub Actions runs the unit and fast mock-integration suites on Python 3.11 and 3.12; Ruff, mypy, wheel build, Docker build, and mechanism demo may run once on Python 3.12. `.gitlab-ci.yml` defines a job named exactly `unit-test` on Python 3.12 that runs `python -m pytest tests/unit tests/integration/test_mock_loop.py`, followed by package and container build jobs. Docker-dependent sandbox tests run only on a runner explicitly labeled/configured for Docker.

```yaml
# .gitlab-ci.yml
stages: [test, build]

unit-test:
  stage: test
  image: python:3.12
  script:
    - python -m pip install -e ".[dev]"
    - python -m pytest tests/unit tests/integration/test_mock_loop.py

package:
  stage: build
  image: python:3.12
  script:
    - python -m pip install build
    - python -m build
  artifacts:
    paths: [dist/]
```

- [ ] **Step 5: Write README and license inventory**

README must contain: project introduction, architecture, installation from PyPI, CLI commands, local WebUI, public demo distinction, Docker commands, OS-keyring setup/status/update/clear, explicit `.env` risks, target-machine secret setup, directory structure, security boundaries, supported platform/architecture, Docker prerequisite, known limitations, one-command tests, mechanism demo, deployment architecture, and CI/CD. `LICENSES.md` lists every direct dependency and the vendored HTMX license.

```markdown
# TestForge

## What TestForge Does
## Architecture
## Install from PyPI
## Initialize a Trusted Project
## Configure Credentials Safely
## Run the CLI
## Run the Local WebUI
## Public Mock Demo
## Docker Distribution
## Testing and Mechanism Demo
## Security Boundaries
## Directory Structure
## Supported Platforms and Prerequisites
## Known Limitations
## Deployment and CI/CD
## Third-Party Licenses
```

- [ ] **Step 6: Run full verification**

Run: `python -m pytest`  
Expected: all non-Docker-required tests PASS with zero failures.  
Run: `python -m ruff check .`  
Expected: exit 0.  
Run: `python -m mypy src`  
Expected: exit 0.  
Run: `python -m build`  
Expected: wheel and source archive under `dist/`.  
Run: `docker build -t testforge:local .`  
Expected: image builds successfully.  
Run: `python scripts/mechanism_demo.py`  
Expected: exit 0 with deterministic JSON.  
Run: `git grep -n -I -E "(sk-[A-Za-z0-9_-]{12,}|OPENAI_API_KEY=.+)" -- . ":(exclude)PLAN.md"`  
Expected: no real-looking credential assignment or token.

- [ ] **Step 7: Update evidence and commit**

Mark every completed task in `PLAN.md` with its commit hash. Append CI/build/test results and human interventions to `AGENT_LOG.md`.

Commit: `git add Dockerfile .dockerignore .github/workflows/ci.yml .gitlab-ci.yml README.md LICENSES.md pyproject.toml AGENT_LOG.md PLAN.md && git commit -m "docs: complete distribution and verification"`

---

## Cold-Start Gate Before Task 1

Implementation is forbidden immediately after this plan is written. Start a new session with an agent type different from the primary Codex agent, provide only `SPEC.md` and `PLAN.md`, and instruct it:

> Select Task 1 and at most one directly dependent task. Work autonomously from SPEC.md and PLAN.md only. If any requirement, interface, command, or expected result is uncertain, pause and ask instead of guessing.

Record every pause, question, divergent interpretation, output difference, and resulting SPEC/PLAN revision in `SPEC_PROCESS.md`. A correct pause before RED is valid cold-start evidence, but the gate is not complete until the documents are revised and approved, the same isolated agent resumes Task 1, and its RED/GREEN output, changed-file list, diff, and commit hash are recorded. Only then may formal implementation begin.

## Per-Task Review Gate

For every task:

1. A fresh implementer follows the listed RED → GREEN steps and commits only that task.
2. A fresh spec reviewer checks the diff against `SPEC.md`, this task, and Global Constraints.
3. The implementer fixes all spec findings.
4. A fresh code-quality reviewer checks correctness, tests, security, maintainability, and scope.
5. The implementer fixes every Critical issue and reruns the task command plus the fast suite.
6. Record implementer/reviewer identity, human edits, verification output, and commit hash in `AGENT_LOG.md` and `PLAN.md`.
