import os
import re
import stat
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from testforge.domain.errors import InputError, StaleWorkspaceError
from testforge.governance.approval import sha256_text


@dataclass(frozen=True)
class _TargetSnapshot:
    identity: tuple[int, int]
    patch_hash: str


class AtomicPatchApplier:
    """Cooperatively serialize writes and reject changes before replacement.

    A non-cooperating editor can still write in the final recheck/replace
    micro-window because portable filesystems do not expose content-based CAS.
    """

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()
        lock_key = sha256_text(os.path.normcase(str(self.repository_root)))
        self._lock_path = (
            Path(tempfile.gettempdir()) / "testforge-project-locks" / f"{lock_key}.lock"
        )

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
        with self._project_lock():
            initial = self._initial_snapshot(target)
            initial_hash = sha256_text("") if initial is None else initial.patch_hash
            if initial_hash != expected_hash:
                raise StaleWorkspaceError("destination changed after validation")
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
            try:
                with temporary.open("w", encoding="utf-8", newline="") as handle:
                    handle.write(new_content)
                    handle.flush()
                    os.fsync(handle.fileno())
                if not self._matches_snapshot(target, initial):
                    raise StaleWorkspaceError("destination changed before replacement")
                # The cooperative lock cannot close the portable final micro-race
                # with editors that do not participate in this lock protocol.
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)

    @contextmanager
    def _project_lock(self) -> Iterator[None]:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            self._acquire_os_lock(handle)
            try:
                yield
            finally:
                self._release_os_lock(handle)

    @staticmethod
    def _acquire_os_lock(handle) -> None:
        if os.name == "nt":
            import msvcrt

            while True:
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    return
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    @staticmethod
    def _release_os_lock(handle) -> None:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _initial_snapshot(self, target: Path) -> _TargetSnapshot | None:
        try:
            before = target.lstat()
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(before.st_mode):
            raise InputError("replacement target must not be a symlink")
        if not stat.S_ISREG(before.st_mode):
            raise InputError("replacement target must be a regular file")
        current = self._read_exact_text(target)
        try:
            after = target.lstat()
        except FileNotFoundError as error:
            raise StaleWorkspaceError(
                "destination changed during validation"
            ) from error
        if not self._same_regular_file(before, after):
            raise StaleWorkspaceError("destination changed during validation")
        return _TargetSnapshot(
            identity=(after.st_dev, after.st_ino),
            patch_hash=sha256_text(current),
        )

    def _matches_snapshot(
        self,
        target: Path,
        expected: _TargetSnapshot | None,
    ) -> bool:
        try:
            before = target.lstat()
        except FileNotFoundError:
            return expected is None
        if expected is None or not stat.S_ISREG(before.st_mode):
            return False
        if (before.st_dev, before.st_ino) != expected.identity:
            return False
        try:
            current = self._read_exact_text(target)
            after = target.lstat()
        except (FileNotFoundError, OSError):
            return False
        return (
            self._same_regular_file(before, after)
            and (after.st_dev, after.st_ino) == expected.identity
            and sha256_text(current) == expected.patch_hash
        )

    @staticmethod
    def _read_exact_text(target: Path) -> str:
        with target.open("r", encoding="utf-8", newline="") as handle:
            return handle.read()

    @staticmethod
    def _same_regular_file(first: os.stat_result, second: os.stat_result) -> bool:
        return (
            stat.S_ISREG(first.st_mode)
            and stat.S_ISREG(second.st_mode)
            and (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)
        )
