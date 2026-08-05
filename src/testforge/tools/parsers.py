import json
import math
from typing import Any
from xml.etree import ElementTree

from testforge.domain.errors import ToolExecutionError
from testforge.domain.models import MetricSnapshot
from testforge.tools.results import (
    CoverageResult,
    MutationResult,
    MutationRunOutcome,
    PytestResult,
)


def parse_pytest_json(raw: str) -> PytestResult:
    try:
        payload = _json_object(raw)
        summary = payload["summary"]
        if not isinstance(summary, dict):
            raise TypeError
        return PytestResult(
            passed=_count(summary, "passed"),
            failed=_count(summary, "failed"),
            skipped=_count(summary, "skipped"),
            errors=_count(summary, "error", default=0),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ToolExecutionError("invalid pytest JSON") from exc


def parse_coverage_json(raw: str, target: str) -> CoverageResult:
    try:
        payload = _json_object(raw)
        files = payload["files"]
        if not isinstance(files, dict):
            raise TypeError
        file_payload = files[target]
        if not isinstance(file_payload, dict):
            raise TypeError
        summary = file_payload["summary"]
        if not isinstance(summary, dict):
            raise TypeError

        display = summary["percent_covered_display"]
        if not isinstance(display, str):
            raise TypeError
        branch_percent = float(display)
        if not math.isfinite(branch_percent) or not 0 <= branch_percent <= 100:
            raise ValueError

        missing_lines = _integer_list(file_payload["missing_lines"])
        missing_branches = _branch_list(file_payload["missing_branches"])
        return CoverageResult(
            branch_percent=branch_percent,
            missing_lines=missing_lines,
            missing_branches=missing_branches,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ToolExecutionError("invalid coverage JSON") from exc


def parse_mutmut_junit(
    raw: str,
    outcome: MutationRunOutcome = MutationRunOutcome.COMPLETED,
) -> MutationResult:
    if outcome is MutationRunOutcome.UNSUPPORTED:
        return MutationResult(supported=False, total=0, killed=0, survived=0, errors=0)
    if outcome is MutationRunOutcome.TIMEOUT:
        raise ToolExecutionError("mutation tool timed out")

    try:
        root = ElementTree.fromstring(raw)
        if _local_name(root.tag) not in {"testsuite", "testsuites"}:
            raise ValueError
        cases = root.findall(".//testcase")
        if not cases:
            raise ValueError

        killed = 0
        survived = 0
        errors = 0
        for case in cases:
            if case.find("error") is not None:
                errors += 1
            elif case.find("failure") is not None:
                killed += 1
            else:
                survived += 1
        return MutationResult(
            supported=True,
            total=len(cases),
            killed=killed,
            survived=survived,
            errors=errors,
        )
    except (ElementTree.ParseError, TypeError, ValueError) as exc:
        raise ToolExecutionError("invalid mutmut JUnit XML") from exc


def metric_snapshot_from_results(
    pytest_result: PytestResult,
    coverage_result: CoverageResult,
    mutation_result: MutationResult,
) -> MetricSnapshot:
    return MetricSnapshot(
        tests_passed=pytest_result.passed,
        tests_failed=pytest_result.failed + pytest_result.errors,
        tests_skipped=pytest_result.skipped,
        branch_coverage=coverage_result.branch_percent,
        mutants_total=mutation_result.total,
        mutants_killed=mutation_result.killed,
        mutants_survived=mutation_result.survived,
        mutation_status="supported" if mutation_result.supported else "unsupported",
    )


def _json_object(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise TypeError
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError
    return payload


def _count(values: dict[str, Any], key: str, default: int | None = None) -> int:
    if key not in values:
        if default is None:
            raise KeyError(key)
        return default
    value = values[key]
    if type(value) is not int or value < 0:
        raise TypeError
    return value


def _integer_list(value: Any) -> tuple[int, ...]:
    if not isinstance(value, list) or any(type(item) is not int for item in value):
        raise TypeError
    return tuple(value)


def _branch_list(value: Any) -> tuple[tuple[int, int], ...]:
    if not isinstance(value, list):
        raise TypeError
    branches: list[tuple[int, int]] = []
    for branch in value:
        if (
            not isinstance(branch, list)
            or len(branch) != 2
            or any(type(item) is not int for item in branch)
        ):
            raise TypeError
        branches.append((branch[0], branch[1]))
    return tuple(branches)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
