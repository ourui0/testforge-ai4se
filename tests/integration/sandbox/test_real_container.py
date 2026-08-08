"""Real-container integration tests — require Docker daemon."""

from pathlib import Path

import pytest

docker = pytest.importorskip("docker")

from testforge.sandbox.docker_runner import DockerSandboxRunner

pytestmark = pytest.mark.docker


# ── fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def fixture_workspace() -> Path:
    """Path to the simple_math fixture project."""
    return Path(__file__).resolve().parents[3] / "fixtures" / "projects" / "simple_math"


# ── real container tests ─────────────────────────────────────────────

def test_real_container_can_write_tests_but_not_source(
    fixture_workspace: Path,
) -> None:
    """Tests dir is writable; source dir is read-only."""
    runner = DockerSandboxRunner(
        docker.from_env(), image="testforge-runner:py312"
    )
    tests = runner.run(
        ("python", "-c", "open('/workspace/tests/generated.txt','w').write('ok')"),
        fixture_workspace,
        30,
    )
    source = runner.run(
        (
            "python",
            "-c",
            "open('/workspace/src/forbidden.txt','w').write('no')",
        ),
        fixture_workspace,
        30,
    )
    assert tests.exit_code == 0
    assert source.exit_code != 0
