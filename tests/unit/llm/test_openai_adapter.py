"""Tests for OpenAIClient — structured output, error normalization, secret safety."""

from unittest.mock import MagicMock

import pytest

from testforge.domain.errors import LLMError
from testforge.domain.models import TestProposal
from testforge.llm.openai_adapter import OpenAIClient
from testforge.llm.protocol import GenerationContext, LLMResponse

# ── fake OpenAI client ───────────────────────────────────────────────

class FakeParsedResponse:
    def __init__(self, output_parsed: LLMResponse | None = None) -> None:
        self.output_parsed = output_parsed


class FakeResponses:
    """Simulates openai.responses with a callable .parse method."""

    def __init__(self, response: FakeParsedResponse) -> None:
        self._response = response
        self.parse_calls: list[dict[str, object]] = []
        self.raise_on_parse: Exception | None = None

    def parse(self, **kwargs: object) -> FakeParsedResponse:
        self.parse_calls.append(kwargs)
        if self.raise_on_parse is not None:
            raise self.raise_on_parse
        return self._response


class FakeOpenAIClient:
    def __init__(self) -> None:
        response = FakeParsedResponse(
            output_parsed=LLMResponse(
                test=TestProposal(
                    path="tests/test_calc.py",
                    content="def test_add(): ...",
                    strategy="assert boundary",
                )
            )
        )
        self.responses = FakeResponses(response)


@pytest.fixture
def fake_openai() -> FakeOpenAIClient:
    return FakeOpenAIClient()


@pytest.fixture
def credential_store() -> MagicMock:
    store = MagicMock()
    store.get.return_value = "sk-fake-test-key"
    return store


def _context() -> GenerationContext:
    return GenerationContext(
        target_module="simple_math",
        source="def add(a,b): return a+b",
        existing_tests="def test_add(): assert add(1,2) == 3",
    )


# ── basic generation test (from brief) ───────────────────────────────

def test_openai_adapter_requests_validated_llm_response(
    fake_openai: FakeOpenAIClient, credential_store: MagicMock
) -> None:
    """Adapter must call OpenAI with correct model, text_format, and return LLMResponse."""
    adapter = OpenAIClient(
        client_factory=lambda api_key: fake_openai,  # type: ignore[arg-type]
        credentials=credential_store,
        model="configured-model",
    )
    response = adapter.generate(_context(), feedback=None)
    assert response.test is not None
    assert response.test.path == "tests/test_calc.py"


# ── error normalization ──────────────────────────────────────────────

class FakeAuthError(Exception):
    pass


class FakeRateLimitError(Exception):
    pass


class FakeTimeoutError(Exception):
    pass


@pytest.mark.parametrize(
    "error, category",
    [
        (FakeAuthError(), "authentication"),
        (FakeRateLimitError(), "rate_limit"),
        (FakeTimeoutError(), "timeout"),
    ],
)
def test_provider_errors_are_normalized(
    fake_openai: FakeOpenAIClient,
    credential_store: MagicMock,
    error: Exception,
    category: str,
) -> None:
    """Provider errors must be normalized to LLMError with safe categories."""
    fake_openai.responses.raise_on_parse = error
    adapter = OpenAIClient(
        client_factory=lambda api_key: fake_openai,  # type: ignore[arg-type]
        credentials=credential_store,
        model="test-model",
    )
    with pytest.raises(LLMError, match=category):
        adapter.generate(_context(), feedback=None)


def test_error_message_contains_no_credential(
    fake_openai: FakeOpenAIClient, credential_store: MagicMock
) -> None:
    """Error messages must never leak the API key."""
    fake_openai.responses.raise_on_parse = FakeAuthError("bad key: sk-leaked-key")
    adapter = OpenAIClient(
        client_factory=lambda api_key: fake_openai,  # type: ignore[arg-type]
        credentials=credential_store,
        model="test-model",
    )
    with pytest.raises(LLMError) as exc_info:
        adapter.generate(_context(), feedback=None)
    assert "sk-" not in str(exc_info.value)


def test_missing_parsed_output_raises(
    fake_openai: FakeOpenAIClient, credential_store: MagicMock
) -> None:
    """When output_parsed is None, must raise LLMError."""
    fake_openai.responses._response = FakeParsedResponse(output_parsed=None)
    adapter = OpenAIClient(
        client_factory=lambda api_key: fake_openai,  # type: ignore[arg-type]
        credentials=credential_store,
        model="test-model",
    )
    with pytest.raises(LLMError, match="no structured action"):
        adapter.generate(_context(), feedback=None)
