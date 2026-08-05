"""Tests for ProjectMemory — structured, bounded, project-isolated memory."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from testforge.domain.errors import PolicyViolation
from testforge.memory import MemoryEntry, ProjectMemory
from testforge.persistence.repository import SQLiteTaskRepository

# ── helpers ──────────────────────────────────────────────────────────

def _utc_now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def repository() -> SQLiteTaskRepository:
    return SQLiteTaskRepository(Path(":memory:"))


@pytest.fixture
def memory(repository: SQLiteTaskRepository) -> ProjectMemory:
    return ProjectMemory(repository)


# ── project isolation (from brief) ───────────────────────────────────

def test_memory_selects_only_same_project_matching_tags(
    memory: ProjectMemory,
) -> None:
    """Cross-project entries must not leak into another project's results."""
    memory.remember("project-a", kind="strategy", tags=("fixture",), summary="use monkeypatch")
    memory.remember("project-b", kind="strategy", tags=("fixture",), summary="foreign")
    result = memory.select("project-a", tags=("fixture",), limit=5)
    assert [entry.summary for entry in result] == ["use monkeypatch"]


# ── secret / source rejection ────────────────────────────────────────

def test_memory_rejects_secret_shaped_content(memory: ProjectMemory) -> None:
    """Summaries containing key-like patterns must be rejected."""
    with pytest.raises(PolicyViolation):
        memory.remember("project-a", kind="strategy", tags=(), summary="sk-secret-value")


def test_memory_rejects_summary_over_2000_chars(memory: ProjectMemory) -> None:
    """Summaries over the character limit must be rejected."""
    long_summary = "x" * 2001
    with pytest.raises(PolicyViolation):
        memory.remember("project-a", kind="note", tags=(), summary=long_summary)


def test_memory_allows_summary_at_2000_chars(memory: ProjectMemory) -> None:
    """Exactly 2000-character summaries are allowed."""
    summary = "y" * 2000
    memory.remember("project-a", kind="note", tags=(), summary=summary)
    result = memory.select("project-a", tags=(), limit=1)
    assert len(result[0].summary) == 2000


# ── bounded selection and tag matching ───────────────────────────────

def test_select_respects_limit(memory: ProjectMemory) -> None:
    """Select returns at most `limit` entries."""
    for i in range(10):
        memory.remember("p", kind="note", tags=("tag",), summary=f"note {i}")
    result = memory.select("p", tags=("tag",), limit=5)
    assert len(result) == 5


def test_select_ranks_by_tag_overlap(memory: ProjectMemory) -> None:
    """Entries matching more tags rank higher in results."""
    memory.remember("p", kind="a", tags=("x",), summary="one-tag")
    memory.remember("p", kind="b", tags=("x", "y"), summary="two-tag")
    memory.remember("p", kind="c", tags=("x", "y", "z"), summary="three-tag")
    result = memory.select("p", tags=("x", "y", "z"), limit=3)
    assert result[0].summary == "three-tag"
    assert result[1].summary == "two-tag"
    assert result[2].summary == "one-tag"


# ── empty / missing cases ────────────────────────────────────────────

def test_select_empty_when_no_entries(memory: ProjectMemory) -> None:
    """Select returns empty tuple when nothing matches."""
    result = memory.select("empty-project", tags=("fixture",), limit=5)
    assert result == ()


def test_list_entries_returns_only_same_project(memory: ProjectMemory) -> None:
    """list_entries is project-scoped."""
    memory.remember("a", kind="note", tags=(), summary="in-a")
    memory.remember("b", kind="note", tags=(), summary="in-b")
    assert [e.summary for e in memory.list_entries("a")] == ["in-a"]
    assert [e.summary for e in memory.list_entries("b")] == ["in-b"]


# ── entry model ──────────────────────────────────────────────────────

def test_memory_entry_is_frozen() -> None:
    """MemoryEntry must be immutable."""
    entry = MemoryEntry(
        project_id="p",
        kind="note",
        tags=(),
        summary="test",
        created_at=_utc_now(),
        version=1,
    )
    with pytest.raises(ValidationError):
        entry.summary = "changed"  # type: ignore[misc]


def test_memory_entry_requires_project_id() -> None:
    """MemoryEntry must have a non-empty project_id."""
    with pytest.raises(ValidationError):
        MemoryEntry(
            project_id="",
            kind="note",
            tags=(),
            summary="test",
            created_at=_utc_now(),
            version=1,
        )


# ── expiry (from brief) ─────────────────────────────────────────────

def test_expired_entries_are_not_selected(memory: ProjectMemory) -> None:
    """Entries past their expiry time must be excluded from select results."""
    past = _utc_now() - timedelta(seconds=1)
    memory.remember("a", kind="strategy", tags=("fixture",), summary="expired", expires_at=past)
    memory.remember("a", kind="strategy", tags=("fixture",), summary="current")
    result = memory.select("a", tags=("fixture",), limit=8)
    assert [entry.summary for entry in result] == ["current"]


def test_expired_entries_not_in_list(memory: ProjectMemory) -> None:
    """list_entries also excludes expired records."""
    past = _utc_now() - timedelta(seconds=1)
    memory.remember("a", kind="note", tags=(), summary="expired", expires_at=past)
    memory.remember("a", kind="note", tags=(), summary="alive")
    summaries = [e.summary for e in memory.list_entries("a")]
    assert "expired" not in summaries
    assert "alive" in summaries


# ── clear project (from brief) ──────────────────────────────────────

def test_clear_is_project_scoped(memory: ProjectMemory) -> None:
    """clear_project removes only the named project's entries."""
    memory.remember("a", kind="strategy", tags=(), summary="remove")
    memory.remember("b", kind="strategy", tags=(), summary="keep")
    memory.clear_project("a")
    assert memory.list_entries("a") == ()
    assert [entry.summary for entry in memory.list_entries("b")] == ["keep"]


# ── capacity boundary ───────────────────────────────────────────────

def test_trim_memory_keeps_at_most_500(memory: ProjectMemory) -> None:
    """Project memory is trimmed to 500 active entries after insertion."""
    for i in range(600):
        memory.remember("cap-test", kind="note", tags=("bulk",), summary=f"s{i}")
    active = memory.list_entries("cap-test")
    assert len(active) <= 500


# ── version and deterministic ordering ──────────────────────────────

def test_select_orders_by_recency_when_tag_overlap_equal(
    memory: ProjectMemory,
) -> None:
    """Entries with equal tag overlap are ordered by recency (newest first)."""
    from time import sleep
    memory.remember("p", kind="a", tags=("t",), summary="older")
    sleep(0.01)
    memory.remember("p", kind="b", tags=("t",), summary="newer")
    result = memory.select("p", tags=("t",), limit=2)
    assert result[0].summary == "newer"
    assert result[1].summary == "older"


def test_select_no_tags_returns_recent(memory: ProjectMemory) -> None:
    """With no tag filter, entries return by recency."""
    from time import sleep
    memory.remember("p", kind="a", tags=(), summary="first")
    sleep(0.01)
    memory.remember("p", kind="b", tags=(), summary="second")
    result = memory.select("p", tags=(), limit=5)
    assert result[0].summary == "second"
    assert result[1].summary == "first"
