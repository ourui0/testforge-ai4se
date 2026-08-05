import pytest
from pydantic import ValidationError

from testforge.domain.errors import LLMError
from testforge.domain.models import FeedbackPacket, RefactorProposal
from testforge.domain.models import TestProposal as Proposal
from testforge.llm import GenerationContext, LLMCall, LLMResponse, MockLLMClient


def TestProposal(*, path: str, content: str, strategy: str) -> Proposal:
    return Proposal(path=path, content=content, strategy=strategy)


def context() -> GenerationContext:
    return GenerationContext(
        target_module="src/calc.py",
        source="def add(left, right):\n    return left + right\n",
        existing_tests="",
    )


def surviving_mutant_feedback() -> FeedbackPacket:
    return FeedbackPacket(
        failure_category="surviving_mutant",
        surviving_mutants=("src/calc.py:2",),
    )


def test_mock_returns_script_in_order_and_records_feedback():
    first = LLMResponse(
        test=TestProposal(
            path="tests/test_calc.py",
            content="def test_one():\n    assert True\n",
            strategy="smoke",
        )
    )
    second = LLMResponse(
        test=TestProposal(
            path="tests/test_calc.py",
            content="def test_one():\n    assert add(1, 1) == 2\n",
            strategy="strong assertion",
        )
    )
    client = MockLLMClient([first, second])
    assert client.generate(context(), feedback=None) == first
    assert client.generate(context(), feedback=surviving_mutant_feedback()) == second
    assert client.calls[1].feedback.failure_category == "surviving_mutant"


def refactor_response() -> LLMResponse:
    return LLMResponse(
        refactor=RefactorProposal(
            path="src/calc.py",
            patch="@@ -1 +1 @@",
            reason="clarify arithmetic",
            risk="low",
        )
    )


def test_response_requires_exactly_one_action():
    test = TestProposal(
        path="tests/test_calc.py",
        content="def test_one():\n    assert True\n",
        strategy="smoke",
    )
    refactor = refactor_response().refactor

    with pytest.raises(
        ValidationError, match="response must contain exactly one action"
    ):
        LLMResponse()
    with pytest.raises(
        ValidationError, match="response must contain exactly one action"
    ):
        LLMResponse(test=test, refactor=refactor)


def test_generation_context_is_immutable_and_rejects_an_empty_target():
    generation_context = context()

    with pytest.raises(ValidationError, match="Instance is frozen"):
        generation_context.source = "changed"
    with pytest.raises(ValidationError):
        GenerationContext(target_module="", source="", existing_tests="")


def test_response_and_recorded_calls_are_immutable():
    response = refactor_response()
    client = MockLLMClient([response])
    client.generate(context(), feedback=None)
    recorded_call = client.calls[0]

    with pytest.raises(ValidationError, match="Instance is frozen"):
        response.refactor = None
    with pytest.raises(ValidationError, match="Instance is frozen"):
        recorded_call.feedback = surviving_mutant_feedback()


def test_mock_copies_responses_and_exposes_read_only_call_snapshots():
    response = refactor_response()
    supplied_responses = [response]
    client = MockLLMClient(supplied_responses)
    supplied_responses.clear()

    assert client.responses == (response,)
    assert client.generate(context(), feedback=None) == response
    calls_snapshot = client.calls
    assert isinstance(calls_snapshot, tuple)
    with pytest.raises(AttributeError):
        client.calls = ()
    calls_snapshot += calls_snapshot
    assert len(client.calls) == 1


def test_exhausted_script_records_every_call_without_advancing_and_raises_exact_error():
    response = refactor_response()
    client = MockLLMClient([response])
    client.generate(context(), feedback=None)

    for expected_call_count in (2, 3):
        with pytest.raises(LLMError, match="^mock script exhausted$"):
            client.generate(context(), feedback=surviving_mutant_feedback())
        assert len(client.calls) == expected_call_count
        assert client._index == 1


def test_empty_script_records_the_call_and_raises_llm_error():
    client = MockLLMClient([])

    with pytest.raises(LLMError, match="^mock script exhausted$"):
        client.generate(context(), feedback=None)

    assert client.calls == (LLMCall(context=context(), feedback=None),)
    assert client._index == 0
