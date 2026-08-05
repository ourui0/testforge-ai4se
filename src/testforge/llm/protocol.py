from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from testforge.domain.models import (
    FeedbackPacket,
    MetricSnapshot,
    RefactorProposal,
    TestProposal,
)


class GenerationContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_module: str = Field(min_length=1)
    source: str
    existing_tests: str
    baseline: MetricSnapshot | None = None
    constraints: tuple[str, ...] = ()
    memory: tuple[str, ...] = ()


class LLMCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    context: GenerationContext
    feedback: FeedbackPacket | None = None


class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    test: TestProposal | None = None
    refactor: RefactorProposal | None = None

    @model_validator(mode="after")
    def exactly_one_action(self) -> "LLMResponse":
        if (self.test is None) == (self.refactor is None):
            raise ValueError("response must contain exactly one action")
        return self


class LLMClient(Protocol):
    def generate(
        self, context: GenerationContext, feedback: FeedbackPacket | None
    ) -> LLMResponse:
        raise NotImplementedError("LLM providers must return one validated action")
