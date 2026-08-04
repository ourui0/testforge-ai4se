import pytest

import testforge.governance.apply as apply_module
from testforge.domain.errors import InputError, StaleWorkspaceError
from testforge.domain.models import TestProposal as Proposal
from testforge.governance.apply import AtomicPatchApplier
from testforge.governance.approval import sha256_text


@pytest.fixture
def applier():
    return AtomicPatchApplier()


@pytest.fixture
def approved_patch():
    return Proposal(
        path="tests/test_math.py",
        content="def test_math():\n    assert 1 + 1 == 2\n",
        strategy="example",
    )


def test_apply_rejects_changed_destination(tmp_path, applier, approved_patch):
    target = tmp_path / "tests/test_math.py"
    target.parent.mkdir()
    target.write_text("user change\n", encoding="utf-8")
    with pytest.raises(StaleWorkspaceError):
        applier.apply_file_replacement(
            target,
            expected_hash=sha256_text("old\n"),
            new_content=approved_patch.content,
        )


def test_apply_replaces_matching_regular_file_atomically(
    tmp_path, applier, approved_patch
):
    target = tmp_path / "test_math.py"
    target.write_bytes(b"old\r\n")

    applier.apply_file_replacement(
        target,
        expected_hash=sha256_text("old\r\n"),
        new_content=approved_patch.content,
    )

    assert target.read_bytes() == approved_patch.content.encode("utf-8")
    assert list(tmp_path.glob(".test_math.py.*.tmp")) == []


def test_apply_creates_missing_file_only_when_parent_exists(tmp_path, applier):
    target = tmp_path / "tests" / "test_new.py"
    target.parent.mkdir()

    applier.apply_file_replacement(
        target,
        expected_hash=sha256_text(""),
        new_content="new\r\ncontent\r\n",
    )

    assert target.read_bytes() == b"new\r\ncontent\r\n"


def test_apply_hashes_existing_crlf_without_newline_normalization(tmp_path, applier):
    target = tmp_path / "test_math.py"
    target.write_bytes(b"old\r\n")

    with pytest.raises(StaleWorkspaceError):
        applier.apply_file_replacement(
            target,
            expected_hash=sha256_text("old\n"),
            new_content="new\n",
        )

    assert target.read_bytes() == b"old\r\n"


@pytest.mark.parametrize(
    "expected_hash",
    [
        "a" * 63,
        "A" * 64,
        "g" * 64,
    ],
)
def test_apply_rejects_invalid_expected_hash(tmp_path, applier, expected_hash):
    target = tmp_path / "test_math.py"
    target.write_text("old", encoding="utf-8")

    with pytest.raises(InputError, match="expected hash"):
        applier.apply_file_replacement(
            target,
            expected_hash=expected_hash,
            new_content="new",
        )

    assert target.read_text(encoding="utf-8") == "old"


def test_apply_refuses_missing_parent_without_creating_it(tmp_path, applier):
    target = tmp_path / "missing" / "test_math.py"

    with pytest.raises(FileNotFoundError):
        applier.apply_file_replacement(
            target,
            expected_hash=sha256_text(""),
            new_content="new",
        )

    assert not target.parent.exists()


def test_apply_rejects_directory_target(tmp_path, applier):
    target = tmp_path / "test_math.py"
    target.mkdir()

    with pytest.raises(InputError, match="regular file"):
        applier.apply_file_replacement(
            target,
            expected_hash=sha256_text(""),
            new_content="new",
        )


def test_apply_rejects_symlink_target(tmp_path, applier):
    destination = tmp_path / "destination.py"
    destination.write_text("old", encoding="utf-8")
    target = tmp_path / "test_math.py"
    try:
        target.symlink_to(destination)
    except OSError:
        pytest.skip("test environment does not permit symlink creation")

    with pytest.raises(InputError, match="symlink"):
        applier.apply_file_replacement(
            target,
            expected_hash=sha256_text("old"),
            new_content="new",
        )

    assert destination.read_text(encoding="utf-8") == "old"


def test_apply_removes_temporary_file_when_replace_fails(
    tmp_path, applier, monkeypatch
):
    target = tmp_path / "test_math.py"
    target.write_text("old", encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(apply_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        applier.apply_file_replacement(
            target,
            expected_hash=sha256_text("old"),
            new_content="new",
        )

    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob(".test_math.py.*.tmp")) == []
