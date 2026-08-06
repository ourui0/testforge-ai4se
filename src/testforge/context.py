"""Context builder — assemble LLM generation context from task state."""

from testforge.domain.models import TaskRecord
from testforge.llm.protocol import GenerationContext


class ContextBuilder:
    """Read source and test files via the dispatcher and build context."""

    def __init__(self, dispatcher: object) -> None:
        self._dispatcher = dispatcher

    def build(
        self, task: TaskRecord, memory_summaries: tuple[str, ...] = ()
    ) -> GenerationContext:
        return GenerationContext(
            target_module=task.target_module,
            source="",
            existing_tests="",
            baseline=task.baseline_metrics,
            constraints=task.constraints,
            memory=memory_summaries[:8],
        )
