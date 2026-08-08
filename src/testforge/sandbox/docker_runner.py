"""Docker sandbox runner — isolated, non-root, offline container execution."""

from pathlib import Path

from testforge.domain.errors import SandboxError
from testforge.tools.results import CommandResult


class DockerSandboxRunner:
    """Run commands inside a restricted Docker container.

    Constraints:
    - Non-root user (65532:65532)
    - Network disabled
    - Read-only root filesystem
    - Memory / CPU / PID limits
    - All capabilities dropped, no-new-privileges
    - /tmp as restricted tmpfs
    - Source tree mounted read-only; tests directory writable
    - Docker socket NOT mounted
    - Timeout with kill + remove
    """

    def __init__(self, client: object, image: str) -> None:
        self._client = client
        self._image = image

    def run(
        self,
        argv: tuple[str, ...],
        workspace: Path,
        timeout_seconds: int,
    ) -> CommandResult:
        tests_dir = workspace / "tests"
        volumes: dict[str, dict[str, str]] = {
            str(workspace): {"bind": "/workspace", "mode": "ro"},
        }
        if tests_dir.exists():
            volumes[str(tests_dir)] = {"bind": "/workspace/tests", "mode": "rw"}

        container = self._client.containers.run(
            self._image,
            list(argv),
            detach=True,
            working_dir="/workspace",
            user="65532:65532",
            network_disabled=True,
            read_only=True,
            mem_limit="512m",
            nano_cpus=1_000_000_000,
            pids_limit=128,
            security_opt=["no-new-privileges:true"],
            cap_drop=["ALL"],
            volumes=volumes,
            tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
        )
        try:
            result = container.wait(timeout=timeout_seconds)
            return CommandResult(
                exit_code=int(result["StatusCode"]),
                stdout=container.logs(stdout=True, stderr=False).decode(
                    errors="replace"
                ),
                stderr=container.logs(stdout=False, stderr=True).decode(
                    errors="replace"
                ),
            )
        except Exception as exc:
            container.kill()
            raise SandboxError(
                "sandbox command timed out or failed"
            ) from exc
        finally:
            container.remove(force=True)

    def cleanup(self) -> None:
        """No-op for stateless runner; containers are removed in run()."""
