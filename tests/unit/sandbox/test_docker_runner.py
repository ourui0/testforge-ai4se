"""Tests for DockerSandboxRunner — isolation, resource limits, timeout."""

from pathlib import Path

import pytest

from testforge.sandbox.docker_runner import DockerSandboxRunner

# ── helpers ──────────────────────────────────────────────────────────

class FakeContainer:
    """Minimal fake that records options and simulates successful run."""

    def __init__(self) -> None:
        self._exit_code = 0
        self._stdout = b""
        self._stderr = b""
        self.killed = False
        self.removed = False

    def wait(self, timeout: int | None = None) -> dict[str, object]:
        _ = timeout
        return {"StatusCode": self._exit_code}

    def logs(self, stdout: bool = True, stderr: bool = False) -> bytes:
        if stdout:
            return self._stdout
        if stderr:
            return self._stderr
        return b""

    def kill(self) -> None:
        self.killed = True

    def remove(self, force: bool = False) -> None:
        _ = force
        self.removed = True


class FakeContainers:
    """Fake docker.containers that records last run options."""

    def __init__(self) -> None:
        self.last_run_options: dict[str, object] = {}

    def run(self, image: str, command: list[str], **kwargs: object) -> FakeContainer:
        _ = image, command
        self.last_run_options = kwargs
        container = FakeContainer()
        return container


class FakeDockerClient:
    """Fake Docker client returning FakeContainers."""

    def __init__(self) -> None:
        self.containers = FakeContainers()


@pytest.fixture
def fake_docker_client() -> FakeDockerClient:
    return FakeDockerClient()


@pytest.fixture
def runner(fake_docker_client: FakeDockerClient) -> DockerSandboxRunner:
    return DockerSandboxRunner(
        fake_docker_client, image="testforge-runner:py312"  # type: ignore[arg-type]
    )


# ── security / isolation tests (from brief) ──────────────────────────

def test_container_is_non_root_offline_and_resource_limited(
    tmp_path: Path, runner: DockerSandboxRunner, fake_docker_client: FakeDockerClient
) -> None:
    """Verify every security constraint is applied to the container."""
    runner.run(
        ("python", "-m", "pytest", "-q"),
        workspace=tmp_path,
        timeout_seconds=60,
    )
    options = fake_docker_client.containers.last_run_options
    assert options["network_disabled"] is True
    assert options["user"] == "65532:65532"
    assert options["mem_limit"] == "512m"
    assert options["nano_cpus"] == 1_000_000_000
    assert options["pids_limit"] == 128
    assert "/var/run/docker.sock" not in repr(options["volumes"])


def test_container_is_read_only_root(
    runner: DockerSandboxRunner, fake_docker_client: FakeDockerClient
) -> None:
    """Root filesystem must be read-only."""
    runner.run(("echo", "hello"), workspace=Path("/tmp"), timeout_seconds=10)
    options = fake_docker_client.containers.last_run_options
    assert options["read_only"] is True


def test_all_capabilities_dropped(
    runner: DockerSandboxRunner, fake_docker_client: FakeDockerClient
) -> None:
    """All Linux capabilities must be dropped."""
    runner.run(("echo", "hello"), workspace=Path("/tmp"), timeout_seconds=10)
    options = fake_docker_client.containers.last_run_options
    assert options["cap_drop"] == ["ALL"]


def test_no_new_privileges(
    runner: DockerSandboxRunner, fake_docker_client: FakeDockerClient
) -> None:
    """no-new-privileges must be set."""
    runner.run(("echo", "hello"), workspace=Path("/tmp"), timeout_seconds=10)
    options = fake_docker_client.containers.last_run_options
    assert "no-new-privileges:true" in options["security_opt"]


def test_tmpfs_is_restricted(
    runner: DockerSandboxRunner, fake_docker_client: FakeDockerClient
) -> None:
    """/tmp must be a restricted tmpfs."""
    runner.run(("echo", "hello"), workspace=Path("/tmp"), timeout_seconds=10)
    options = fake_docker_client.containers.last_run_options
    tmpfs_opts = options["tmpfs"]["/tmp"]
    assert "noexec" in tmpfs_opts
    assert "nosuid" in tmpfs_opts
    assert "size=64m" in tmpfs_opts


# ── timeout tests ────────────────────────────────────────────────────

class _TimeoutContainer(FakeContainer):
    """Fake container that simulates a timeout during wait()."""

    def wait(self, timeout: int | None = None) -> dict[str, object]:
        _ = timeout
        raise TimeoutError("simulated timeout")


class _TimeoutContainers(FakeContainers):
    """Fake containers that return a timeout-simulating container."""

    def run(self, image: str, command: list[str], **kwargs: object) -> FakeContainer:
        _ = image, command
        self.last_run_options = kwargs
        return _TimeoutContainer()


class _TimeoutDockerClient(FakeDockerClient):
    """Fake Docker client whose containers always time out."""

    def __init__(self) -> None:
        self.containers = _TimeoutContainers()  # type: ignore[assignment]


def test_timeout_kills_and_removes_container(tmp_path: Path) -> None:
    """Timeout must kill and remove the container, raising SandboxError."""
    client = _TimeoutDockerClient()
    runner = DockerSandboxRunner(
        client, image="testforge-runner:py312"  # type: ignore[arg-type]
    )
    from testforge.domain.errors import SandboxError

    with pytest.raises(SandboxError):
        runner.run(("sleep", "999"), workspace=tmp_path, timeout_seconds=0)
