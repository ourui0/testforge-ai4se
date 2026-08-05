from collections.abc import Sequence

from testforge.domain.errors import LLMError
from testforge.domain.models import FeedbackPacket
from testforge.llm.protocol import GenerationContext, LLMCall, LLMResponse


class MockLLMClient:
    def __init__(self, responses: Sequence[LLMResponse]) -> None:
        self.responses: tuple[LLMResponse, ...] = tuple(responses)
        self._calls: list[LLMCall] = []
        self._index = 0

    @property
    def calls(self) -> tuple[LLMCall, ...]:
        return tuple(self._calls)

    def generate(
        self, context: GenerationContext, feedback: FeedbackPacket | None
    ) -> LLMResponse:
        self._calls.append(LLMCall(context=context, feedback=feedback))
        if self._index >= len(self.responses):
            raise LLMError("mock script exhausted")
        response = self.responses[self._index]
        self._index += 1
        return response
