"""Project image builder — dependency fingerprinting and Dockerfile rendering."""

import hashlib
from pathlib import Path

_DEPENDENCY_FILES = ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg")
_TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "docker" / "project-runner.Dockerfile.template"


class ProjectImageBuilder:
    """Fingerprint project dependencies and render the Dockerfile template.

    The fingerprint only considers dependency-manifest files so that
    source-only changes do not trigger a rebuild.
    """

    def fingerprint(self, project_root: Path) -> str:
        """Return a hex digest of the project's dependency configuration."""
        hasher = hashlib.sha256()
        for name in sorted(_DEPENDENCY_FILES):
            path = project_root / name
            if not path.is_file():
                continue
            hasher.update(name.encode())
            hasher.update(path.read_bytes())
        return hasher.hexdigest()

    def render_dockerfile(self, project_root: Path) -> str:
        """Read the templated Dockerfile and return it as a string."""
        _ = project_root  # reserved for future template variable substitution
        return _TEMPLATE_PATH.read_text(encoding="utf-8")

    def build(
        self, project_root: Path, *, trusted_project: bool = False
    ) -> str:
        """Build the project image (placeholder — real build in integration).

        Returns the image tag that would be used.
        """
        if not trusted_project:
            raise ValueError(
                "trusted_project must be True to build a project image"
            )
        tag = f"testforge-project:{self.fingerprint(project_root)}"
        # In a full implementation this would call docker-py's build;
        # for unit tests the render_dockerfile path is sufficient.
        return tag
