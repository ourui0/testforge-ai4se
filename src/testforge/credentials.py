"""Secure credential store — keyring-first with explicit dotenv fallback."""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

from testforge.domain.errors import CredentialError


class CredentialStatus(BaseModel):
    """Immutable status snapshot — never contains the raw secret."""

    model_config = ConfigDict(frozen=True)

    provider: str
    configured: bool
    source: str | None = None


class CredentialStore:
    """Store and retrieve API credentials via OS keyring.

    Design:
    - keyring is the primary store; dotenv is an opt-in fallback.
    - status() and repr() never expose the secret value.
    - clear() is idempotent when the entry is already missing.
    """

    def __init__(
        self,
        backend: Any,
        service_name: str,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._backend = backend
        self._service_name = service_name
        self._environment: dict[str, str] = dict(environment or {})

    def set(self, provider: str, secret: str) -> None:
        if not secret.strip():
            raise CredentialError("credential cannot be empty")
        self._backend.set_password(self._service_name, provider, secret)

    def status(self, provider: str) -> CredentialStatus:
        configured = (
            self._backend.get_password(self._service_name, provider) is not None
        )
        return CredentialStatus(
            provider=provider,
            configured=configured,
            source="keyring" if configured else None,
        )

    def get(self, provider: str, allow_dotenv: bool = False) -> str:
        secret = self._backend.get_password(self._service_name, provider)
        if secret is None and allow_dotenv:
            secret = self._environment.get("OPENAI_API_KEY")
        if secret is None:
            raise CredentialError(
                f"credential for {provider} is not configured"
            )
        return secret

    def clear(self, provider: str) -> None:
        try:
            self._backend.delete_password(self._service_name, provider)
        except (KeyError, AttributeError, RuntimeError):
            # Idempotent — missing entry or unsupported backend is not an error
            return
