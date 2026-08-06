"""OpenAI LLM adapter — structured output, provider-neutral errors."""

from testforge.domain.errors import LLMError
from testforge.llm.protocol import (
    FeedbackPacket,
    GenerationContext,
    LLMResponse,
)


class OpenAIClient:
    """Provider-neutral adapter over OpenAI Responses API.

    Credentials are fetched from the CredentialStore. Errors are
    normalized to LLMError with safe category strings — never
    exposing provider messages that might contain secrets.
    """

    def __init__(
        self,
        client_factory: object,
        credentials: object,
        model: str,
    ) -> None:
        self._client_factory = client_factory
        self._credentials = credentials
        self._model = model

    def generate(
        self, context: GenerationContext, feedback: FeedbackPacket | None
    ) -> LLMResponse:
        api_key = self._credentials.get("openai")
        client = self._client_factory(api_key=api_key)
        try:
            parsed = client.responses.parse(
                model=self._model,
                input=self._build_input(context, feedback),
                text_format=LLMResponse,
            )
            if parsed.output_parsed is None:
                raise LLMError("no structured action")
            return parsed.output_parsed
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(self._safe_category(exc)) from exc

    # ── internal ──────────────────────────────────────────────────

    @staticmethod
    def _build_input(
        context: GenerationContext, feedback: FeedbackPacket | None
    ) -> str:
        parts = [
            f"Target module: {context.target_module}",
            f"Source:\n{context.source}",
            f"Existing tests:\n{context.existing_tests}",
        ]
        if context.constraints:
            parts.append("Constraints:\n" + "\n".join(context.constraints))
        if context.memory:
            parts.append("Memory:\n" + "\n".join(context.memory))
        if feedback is not None:
            parts.append(
                f"Feedback ({feedback.failure_category}): "
                + "; ".join(feedback.constraints_for_next_attempt)
            )
        return "\n\n".join(parts)

    @staticmethod
    def _safe_category(exc: Exception) -> str:
        name = type(exc).__name__.lower()
        if "auth" in name or "401" in str(exc):
            return "authentication"
        if "rate" in name or "429" in str(exc):
            return "rate_limit"
        if "timeout" in name:
            return "timeout"
        return "invalid_response"
