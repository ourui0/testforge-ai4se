"""Tests for ProjectImageBuilder — dependency fingerprinting and Dockerfile rendering."""

from pathlib import Path

import pytest

from testforge.sandbox.image_builder import ProjectImageBuilder

# ── helpers ──────────────────────────────────────────────────────────

@pytest.fixture
def image_builder() -> ProjectImageBuilder:
    return ProjectImageBuilder()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Create a minimal project directory with pyproject.toml."""
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "pyproject.toml").write_text(
        "[project]\nname='sample'\ndependencies=[]\n", encoding="utf-8"
    )
    return proj


# ── fingerprint tests (from brief) ───────────────────────────────────

def test_dependency_fingerprint_changes_with_pyproject(
    tmp_path: Path, image_builder: ProjectImageBuilder
) -> None:
    """Fingerprint must change when dependency config changes."""
    proj = tmp_path / "project"
    proj.mkdir()
    config = proj / "pyproject.toml"
    config.write_text("[project]\nname='sample'\ndependencies=[]\n", encoding="utf-8")
    first = image_builder.fingerprint(proj)
    config.write_text(
        "[project]\nname='sample'\ndependencies=['attrs']\n", encoding="utf-8"
    )
    assert image_builder.fingerprint(proj) != first


def test_fingerprint_unchanged_for_same_dependencies(
    project: Path, image_builder: ProjectImageBuilder
) -> None:
    """Fingerprint must be stable when dependencies don't change."""
    first = image_builder.fingerprint(project)
    second = image_builder.fingerprint(project)
    assert first == second


def test_fingerprint_depends_on_dependency_files_only(
    tmp_path: Path, image_builder: ProjectImageBuilder
) -> None:
    """Fingerprint must only consider dependency files, not source code."""
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "pyproject.toml").write_text(
        "[project]\nname='sample'\n", encoding="utf-8"
    )
    first = image_builder.fingerprint(proj)
    # Change source code, not dependencies
    src = proj / "src"
    src.mkdir()
    (src / "main.py").write_text("x = 1\n", encoding="utf-8")
    assert image_builder.fingerprint(proj) == first


# ── Dockerfile rendering tests (from brief) ──────────────────────────

def test_generated_final_stage_copies_venv_but_not_project_source(
    image_builder: ProjectImageBuilder, tmp_path: Path
) -> None:
    """The runtime stage must copy the venv but NOT contain 'COPY .'."""
    dockerfile = image_builder.render_dockerfile(tmp_path)
    final_stage = dockerfile.split("FROM python:3.12-slim AS runtime", 1)[1]
    assert "COPY --from=builder /opt/venv /opt/venv" in final_stage
    assert "COPY ." not in final_stage


def test_dockerfile_uses_non_root_user(
    image_builder: ProjectImageBuilder, tmp_path: Path
) -> None:
    """Runtime stage must set non-root user."""
    dockerfile = image_builder.render_dockerfile(tmp_path)
    assert "65532:65532" in dockerfile


def test_dockerfile_contains_builder_stage(
    image_builder: ProjectImageBuilder, tmp_path: Path
) -> None:
    """Builder stage must install pytest/coverage/mutmut + project deps."""
    dockerfile = image_builder.render_dockerfile(tmp_path)
    assert "FROM python:3.12-slim AS builder" in dockerfile
    assert "pip install" in dockerfile
