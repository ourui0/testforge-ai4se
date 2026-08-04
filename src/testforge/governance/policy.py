from pathlib import Path

from testforge.config import ProjectConfig, TaskBudget
from testforge.domain.errors import PolicyViolation
from testforge.domain.models import BudgetUsage, RefactorProposal, TestProposal


class GovernancePolicy:
    def __init__(
        self,
        config: ProjectConfig,
        max_patch_bytes: int = 65536,
        max_patch_lines: int = 600,
    ) -> None:
        self.repository_root = config.repository_root.resolve()
        self._require_repository_relative(config.tests_root)
        self._require_repository_relative(config.target_module)
        self.tests_root = config.tests_root
        self.target_module = config.target_module
        self.max_patch_bytes = max_patch_bytes
        self.max_patch_lines = max_patch_lines

    def validate_read(self, relative_path: str) -> Path:
        requested_path = Path(relative_path)
        self._require_repository_relative(requested_path)

        candidate = (self.repository_root / requested_path).resolve(strict=False)
        if not candidate.is_relative_to(self.repository_root):
            raise PolicyViolation("path is outside repository")
        return candidate

    def validate_test_proposal(self, proposal: TestProposal) -> Path:
        candidate = self.validate_read(proposal.path)
        tests_root = (self.repository_root / self.tests_root).resolve()
        if not candidate.is_relative_to(tests_root):
            raise PolicyViolation("candidate is outside configured test directory")
        if not proposal.content and candidate.is_file():
            raise PolicyViolation("candidate is a deletion of an existing test")
        self._validate_patch(proposal.content)
        return candidate

    def validate_refactor_proposal(self, proposal: RefactorProposal) -> Path:
        candidate = self.validate_read(proposal.path)
        target = self.validate_read(self.target_module)
        if candidate != target:
            raise PolicyViolation("candidate is outside configured target module")
        self._validate_patch(proposal.patch)
        return candidate

    def validate_budget(self, usage: BudgetUsage, budget: TaskBudget) -> None:
        if usage.attempts >= budget.max_attempts:
            raise PolicyViolation("attempt budget is exhausted")
        if usage.llm_calls >= budget.max_llm_calls:
            raise PolicyViolation("LLM-call budget is exhausted")
        if usage.active_seconds >= budget.max_active_seconds:
            raise PolicyViolation("active-time budget is exhausted")
        if usage.mutants >= budget.max_mutants:
            raise PolicyViolation("mutant budget is exhausted")

    def _validate_patch(self, patch: str) -> None:
        if not patch:
            raise PolicyViolation("candidate patch must be non-empty")
        if len(patch.encode("utf-8")) > self.max_patch_bytes:
            raise PolicyViolation("candidate exceeds patch byte limit")
        if len(patch.splitlines()) > self.max_patch_lines:
            raise PolicyViolation("candidate exceeds patch line limit")

    @staticmethod
    def _require_repository_relative(path: str | Path) -> None:
        requested_path = Path(path)
        if requested_path.anchor:
            raise PolicyViolation("path must be repository-relative")
