"""Application service — composition root and use-case orchestration."""

from pathlib import Path
from typing import Any


def build_application(db_path: Path, **overrides: Any) -> Any:
    """Assemble the full application from components.

    Returns an ApplicationService ready for CLI/WebUI use.
    """
    # Placeholder — full wiring in later tasks
    raise NotImplementedError("build_application requires complete service wiring")
