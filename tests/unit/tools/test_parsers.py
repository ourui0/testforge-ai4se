from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from testforge.domain.errors import ToolExecutionError
from testforge.tools.parsers import (
    metric_snapshot_from_results,
    parse_coverage_json,
    parse_mutmut_junit,
    parse_pytest_json,
)
from testforge.tools.results import CommandResult, MutationResult, MutationRunOutcome

FIXTURE_DIRECTORY = Path(__file__).parents[2] / "fixtures" / "tool_output"


@pytest.fixture
def fixture_text() -> Callable[[str], str]:
    return lambda name: (FIXTURE_DIRECTORY / name).read_text(encoding="utf-8")


def test_parse_tools_into_one_metric_snapshot(fixture_text):
    pytest_result = parse_pytest_json(fixture_text("pytest.json"))
    coverage_result = parse_coverage_json(
        fixture_text("coverage.json"), target="src/calc.py"
    )
    mutation_result = parse_mutmut_junit(fixture_text("mutmut.xml"))
    snapshot = metric_snapshot_from_results(
        pytest_result, coverage_result, mutation_result
    )
    assert (snapshot.tests_passed, snapshot.tests_failed, snapshot.tests_skipped) == (
        8,
        0,
        0,
    )
    assert snapshot.branch_coverage == 75.0
    assert (
        snapshot.mutants_total,
        snapshot.mutants_killed,
        snapshot.mutants_survived,
    ) == (4, 3, 1)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ('{"summary":{"passed":"8","failed":0,"skipped":0}}', "invalid pytest JSON"),
        ('{"summary":{"passed":true,"failed":0,"skipped":0}}', "invalid pytest JSON"),
        ('{"summary":{"passed":8,"failed":0}}', "invalid pytest JSON"),
        ('{"summary":[]}', "invalid pytest JSON"),
        ("not JSON and sk-secret", "invalid pytest JSON"),
    ],
)
def test_pytest_parser_rejects_malformed_or_non_integer_summary(raw, message):
    with pytest.raises(ToolExecutionError) as caught:
        parse_pytest_json(raw)

    assert str(caught.value) == message
    assert raw not in str(caught.value)


def test_pytest_parser_folds_errors_into_failed_metric():
    pytest_result = parse_pytest_json(
        '{"summary":{"passed":4,"failed":2,"skipped":1,"error":3}}'
    )
    coverage_result = parse_coverage_json(
        '{"files":{"src/calc.py":{"summary":{"percent_covered_display":"50"},'
        '"missing_lines":[],"missing_branches":[]}}}',
        target="src/calc.py",
    )
    mutation_result = parse_mutmut_junit("<testsuite><testcase /></testsuite>")

    snapshot = metric_snapshot_from_results(
        pytest_result, coverage_result, mutation_result
    )

    assert snapshot.tests_failed == 5


def test_coverage_parser_preserves_missing_lines_and_branches():
    result = parse_coverage_json(
        '{"files":{"src/calc.py":{"summary":{"percent_covered_display":"75"},'
        '"missing_lines":[4,9],"missing_branches":[[2,5],[8,9]]}}}',
        target="src/calc.py",
    )

    assert result.missing_lines == (4, 9)
    assert result.missing_branches == ((2, 5), (8, 9))


@pytest.mark.parametrize(
    "raw",
    [
        (
            '{"files":{"src/calc.py":{"summary":{"percent_covered_display":75},'
            '"missing_lines":[],"missing_branches":[]}}}'
        ),
        (
            '{"files":{"src/calc.py":{"summary":{"percent_covered_display":"75"},'
            '"missing_lines":[true],"missing_branches":[]}}}'
        ),
        (
            '{"files":{"src/calc.py":{"summary":{"percent_covered_display":"75"},'
            '"missing_lines":[],"missing_branches":[[1]]}}}'
        ),
        '{"files":[]}',
        "not JSON and C:\\\\private\\\\workspace",
    ],
)
def test_coverage_parser_rejects_malformed_or_structurally_invalid_input(raw):
    with pytest.raises(ToolExecutionError) as caught:
        parse_coverage_json(raw, target="src/calc.py")

    assert str(caught.value) == "invalid coverage JSON"
    assert raw not in str(caught.value)


def test_mutation_result_enforces_supported_count_invariant():
    with pytest.raises(ValidationError):
        MutationResult(supported=True, total=4, killed=2, survived=1, errors=0)


def test_mutation_result_requires_zero_counts_when_unsupported():
    with pytest.raises(ValidationError):
        MutationResult(supported=False, total=1, killed=0, survived=1, errors=0)


def test_mutmut_parser_returns_unsupported_only_for_explicit_outcome():
    result = parse_mutmut_junit("not XML", outcome=MutationRunOutcome.UNSUPPORTED)

    assert result == MutationResult(
        supported=False,
        total=0,
        killed=0,
        survived=0,
        errors=0,
    )


def test_mutmut_timeout_is_a_stable_tool_error():
    with pytest.raises(ToolExecutionError, match="^mutation tool timed out$"):
        parse_mutmut_junit("not XML", outcome=MutationRunOutcome.TIMEOUT)


def test_mutmut_parser_classifies_errors_separately_from_killed_and_survived():
    result = parse_mutmut_junit(
        "<testsuite><testcase><failure /></testcase><testcase><error /></testcase>"
        "<testcase /></testsuite>"
    )

    assert (result.total, result.killed, result.survived, result.errors) == (3, 1, 1, 1)


@pytest.mark.parametrize("raw", ["not XML and sk-secret", "<testsuite />"])
def test_mutmut_parser_rejects_malformed_or_empty_junit(raw):
    with pytest.raises(ToolExecutionError) as caught:
        parse_mutmut_junit(raw)

    assert str(caught.value) == "invalid mutmut JUnit XML"
    assert raw not in str(caught.value)


def test_unsupported_mutation_maps_to_unsupported_snapshot():
    pytest_result = parse_pytest_json('{"summary":{"passed":1,"failed":0,"skipped":0}}')
    coverage_result = parse_coverage_json(
        '{"files":{"src/calc.py":{"summary":{"percent_covered_display":"100"},'
        '"missing_lines":[],"missing_branches":[]}}}',
        target="src/calc.py",
    )
    mutation_result = parse_mutmut_junit("", outcome=MutationRunOutcome.UNSUPPORTED)

    snapshot = metric_snapshot_from_results(
        pytest_result, coverage_result, mutation_result
    )

    assert snapshot.mutation_status == "unsupported"


def test_command_diagnostic_redacts_workspace_variants_case_insensitively():
    command = CommandResult(
        exit_code=1,
        stdout="C:\\Work\\Repo\\a.py c:/work/repo/b.py C:/WORK/REPO/c.py",
        stderr="c:\\work\\repo\\d.py",
    )

    summary = command.diagnostic_summary(Path("C:\\Work\\Repo"))

    assert "C:\\Work\\Repo" not in summary
    assert "c:/work/repo" not in summary
    assert "C:/WORK/REPO" not in summary
    assert summary.count("<workspace>") == 4


def test_command_diagnostic_redacts_secrets_before_truncating():
    raw = "sk-" + "a" * 2100 + " visible-tail"
    command = CommandResult(exit_code=0, stdout=raw)

    summary = command.diagnostic_summary()

    assert "<redacted> visible-tail" in summary
    assert "…<truncated>" not in summary


def test_command_diagnostic_redacts_workspace_before_truncating():
    raw = ("C:\\Work\\Repo\\" * 150) + "visible-tail"
    command = CommandResult(exit_code=0, stdout=raw)

    summary = command.diagnostic_summary(Path("C:\\Work\\Repo"))

    assert "visible-tail" in summary
    assert "…<truncated>" not in summary


def test_command_diagnostic_leaves_raw_streams_unchanged():
    command = CommandResult(
        exit_code=2,
        stdout="C:\\Work\\Repo sk-secret",
        stderr="sk-other",
    )

    command.diagnostic_summary(Path("C:\\Work\\Repo"))

    assert command.stdout == "C:\\Work\\Repo sk-secret"
    assert command.stderr == "sk-other"


def test_command_diagnostic_truncates_each_redacted_stream_deterministically():
    command = CommandResult(exit_code=7, stdout="a" * 2001, stderr="b" * 2001)

    summary = command.diagnostic_summary()

    assert summary == (
        "exit_code: 7\nstdout:\n"
        + "a" * 2000
        + "…<truncated>\nstderr:\n"
        + "b" * 2000
        + "…<truncated>"
    )
