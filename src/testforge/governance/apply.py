import os
import re
from pathlib import Path
from uuid import uuid4

from testforge.domain.errors import InputError, StaleWorkspaceError
from testforge.governance.approval import sha256_text


class AtomicPatchApplier:
    def apply_file_replacement(
        self,
        target: Path,
        expected_hash: str,
        new_content: str,
    ) -> None:
        if re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
            raise InputError(
                "expected hash must be 64 lowercase hexadecimal characters"
            )
        if target.is_symlink():
            raise InputError("replacement target must not be a symlink")
        if target.exists() and not target.is_file():
            raise InputError("replacement target must be a regular file")
        if target.exists():
            with target.open("r", encoding="utf-8", newline="") as handle:
                current = handle.read()
        else:
            current = ""
        if sha256_text(current) != expected_hash:
            raise StaleWorkspaceError("destination changed after validation")
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                handle.write(new_content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
