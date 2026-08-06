"""Tests for CredentialStore — keyring-first, no secret leakage."""


import pytest

from testforge.credentials import CredentialStatus, CredentialStore
from testforge.domain.errors import CredentialError

# ── fake keyring backend ─────────────────────────────────────────────

class FakeKeyring:
    """In-memory keyring backend for testing."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, str]] = {}
        self.saved: tuple[str, str, str] | None = None
        self.deleted: tuple[str, str] | None = None

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store.setdefault(service, {})[username] = password
        self.saved = (service, username, password)

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get(service, {}).get(username)

    def delete_password(self, service: str, username: str) -> None:
        self._store.get(service, {}).pop(username, None)
        self.deleted = (service, username)


@pytest.fixture
def fake_keyring() -> FakeKeyring:
    return FakeKeyring()


@pytest.fixture
def store(fake_keyring: FakeKeyring) -> CredentialStore:
    return CredentialStore(fake_keyring, service_name="testforge")


# ── set / status (from brief) ────────────────────────────────────────

def test_status_never_returns_secret(fake_keyring: FakeKeyring) -> None:
    """Status must confirm configured without leaking the secret value."""
    store = CredentialStore(fake_keyring, service_name="testforge")
    store.set("openai", "sk-example-not-real")
    status = store.status("openai")
    assert status.configured is True
    assert "sk-example" not in repr(status)


def test_set_persists_to_keyring(fake_keyring: FakeKeyring) -> None:
    """set must store the credential via the keyring backend."""
    store = CredentialStore(fake_keyring, service_name="testforge")
    store.set("openai", "sk-abcdefg")
    assert fake_keyring.get_password("testforge", "openai") == "sk-abcdefg"


def test_set_rejects_empty_secret(store: CredentialStore) -> None:
    """Empty or whitespace-only credentials must be rejected."""
    with pytest.raises(CredentialError):
        store.set("openai", "")
    with pytest.raises(CredentialError):
        store.set("openai", "   ")


# ── get / fallback ───────────────────────────────────────────────────

def test_get_returns_keyring_value(store: CredentialStore) -> None:
    """get must retrieve the stored credential from keyring."""
    store.set("openai", "sk-my-key")
    assert store.get("openai") == "sk-my-key"


def test_get_raises_when_not_configured(store: CredentialStore) -> None:
    """get must raise CredentialError when no credential is stored."""
    with pytest.raises(CredentialError):
        store.get("openai")


def test_dotenv_fallback_only_with_opt_in(fake_keyring: FakeKeyring) -> None:
    """Environment fallback must require explicit allow_dotenv=True."""
    store = CredentialStore(
        fake_keyring, "testforge",
        environment={"OPENAI_API_KEY": "sk-from-env"},
    )
    # Without opt-in: raises
    with pytest.raises(CredentialError):
        store.get("openai", allow_dotenv=False)
    # With opt-in: returns env value
    assert store.get("openai", allow_dotenv=True) == "sk-from-env"


# ── clear ────────────────────────────────────────────────────────────

def test_clear_removes_stored_credential(store: CredentialStore) -> None:
    """clear must remove the stored credential."""
    store.set("openai", "sk-test")
    store.clear("openai")
    assert store.status("openai").configured is False


def test_clear_missing_is_idempotent(store: CredentialStore) -> None:
    """Clearing a non-existent credential must not raise."""
    store.clear("openai")
    store.clear("openai")  # Idempotent
    assert store.status("openai").configured is False


# ── CredentialStatus model ───────────────────────────────────────────

def test_credential_status_is_frozen() -> None:
    """CredentialStatus must be immutable."""
    from pydantic import ValidationError
    s = CredentialStatus(provider="openai", configured=True, source="keyring")
    with pytest.raises(ValidationError):
        s.configured = False  # type: ignore[misc]


def test_credential_status_repr_contains_no_secret() -> None:
    """repr(CredentialStatus) must never include credential values."""
    s = CredentialStatus(provider="openai", configured=True, source="keyring")
    r = repr(s)
    assert "sk-" not in r
    assert "secret" not in r.lower()
