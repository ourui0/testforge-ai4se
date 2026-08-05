import re
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_DIAGNOSTIC_STREAM_LIMIT = 2000
_TRUNCATION_MARKER = "…<truncated>"
_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]+")


class CommandResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    exit_code: int
    stdout: str = ""
    stderr: str = ""

    def diagnostic_summary(self, workspace_root: Path | None = None) -> str:
        stdout = _diagnostic_stream(self.stdout, workspace_root)
        stderr = _diagnostic_stream(self.stderr, workspace_root)
        return f"exit_code: {self.exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"


class PytestResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(default=0, ge=0)


class CoverageResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    branch_percent: float = Field(ge=0, le=100, allow_inf_nan=False)
    missing_lines: tuple[int, ...] = ()
    missing_branches: tuple[tuple[int, int], ...] = ()

    @field_validator("branch_percent", mode="before")
    @classmethod
    def normalize_branch_percent(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("branch percent must be numeric")  # noqa: TRY004
        return float(value)


class MutationRunOutcome(StrEnum):
    COMPLETED = "completed"
    UNSUPPORTED = "unsupported"
    TIMEOUT = "timeout"


class MutationResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    supported: bool
    total: int = Field(ge=0)
    killed: int = Field(ge=0)
    survived: int = Field(ge=0)
    errors: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.supported and self.total != self.killed + self.survived + self.errors:
            raise ValueError("supported mutation counts must add up to total")
        if not self.supported and any(
            (self.total, self.killed, self.survived, self.errors)
        ):
            raise ValueError("unsupported mutation counts must all be zero")
        return self


def _diagnostic_stream(raw: str, workspace_root: Path | None) -> str:
    redacted = _redact_workspace(raw, workspace_root)
    redacted = _SECRET_PATTERN.sub("<redacted>", redacted)
    if len(redacted) > _DIAGNOSTIC_STREAM_LIMIT:
        return redacted[:_DIAGNOSTIC_STREAM_LIMIT] + _TRUNCATION_MARKER
    return redacted


def _redact_workspace(raw: str, workspace_root: Path | None) -> str:
    if workspace_root is None:
        return raw

    native = str(workspace_root)
    variants = {native, native.replace("\\", "/"), native.replace("/", "\\")}
    variants.discard("")
    if not variants:
        return raw

    pattern = "|".join(
        re.escape(value) for value in sorted(variants, key=len, reverse=True)
    )
    return re.sub(pattern, "<workspace>", raw, flags=re.IGNORECASE)
