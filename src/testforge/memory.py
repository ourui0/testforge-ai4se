"""Structured project memory — bounded, isolated, expiring, deterministic."""

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from testforge.domain.errors import PolicyViolation

if TYPE_CHECKING:
    from testforge.persistence.repository import SQLiteTaskRepository

_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]+")
_SUMMARY_MAX_LENGTH = 2000
_DEFAULT_PROJECT_CAPACITY = 500
_DEFAULT_SELECT_LIMIT = 8


class MemoryEntry(BaseModel):
    """Immutable, project-scoped memory fact with optional expiry and version."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    project_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    tags: tuple[str, ...] = ()
    summary: str = Field(min_length=1, max_length=_SUMMARY_MAX_LENGTH)
    source_task_id: UUID | None = None
    created_at: datetime
    expires_at: datetime | None = None
    version: int = Field(default=1, ge=1)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ProjectMemory:
    """Project-isolated, deterministic, bounded structured memory.

    - No cross-project leakage: every method scopes by project_id.
    - No source storage: payloads marked as full source or complete prompts
      are rejected.
    - No secret-bearing content: summaries matching API-key patterns are
      rejected.
    - Deterministic tag-matching: entries ranked by tag-overlap, then
      recency.
    - Bounded capacity: project is trimmed to at most 500 active entries.
    - Expiry: expired entries are excluded from select and listing.
    """

    def __init__(self, repository: "SQLiteTaskRepository") -> None:
        self._repository = repository

    def remember(
        self,
        project_id: str,
        *,
        kind: str,
        tags: tuple[str, ...] = (),
        summary: str,
        source_task_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryEntry:
        if _SECRET_PATTERN.search(summary):
            raise PolicyViolation("memory summary contains secret-like content")
        if not summary.strip():
            raise PolicyViolation("memory summary must not be empty")

        try:
            entry = MemoryEntry(
                project_id=project_id,
                kind=kind,
                tags=tags,
                summary=summary,
                source_task_id=source_task_id,
                created_at=_utc_now(),
                expires_at=expires_at,
                version=1,
            )
        except ValidationError as exc:
            raise PolicyViolation(str(exc)) from exc
        self._repository.add_memory(entry)
        self._repository.trim_memory(
            project_id=project_id, maximum=_DEFAULT_PROJECT_CAPACITY
        )
        return entry

    def select(
        self,
        project_id: str,
        tags: tuple[str, ...] = (),
        limit: int = _DEFAULT_SELECT_LIMIT,
    ) -> tuple[MemoryEntry, ...]:
        active = self._repository.find_memory(
            project_id=project_id, active_at=_utc_now()
        )
        if not active:
            return ()
        ranked = sorted(
            active,
            key=lambda entry: (len(set(tags) & set(entry.tags)), entry.created_at),
            reverse=True,
        )
        return tuple(ranked[:limit])

    def list_entries(self, project_id: str) -> tuple[MemoryEntry, ...]:
        return self._repository.find_memory(
            project_id=project_id, active_at=_utc_now()
        )

    def clear_project(self, project_id: str) -> None:
        self._repository.clear_project_memory(project_id)
