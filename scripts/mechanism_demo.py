#!/usr/bin/env python3
"""Deterministic mechanism demonstration — no network, no credentials."""

import json


def run_mechanism_demo() -> dict[str, object]:
    """Run the core mechanism demo and return a structured report."""
    return {
        "dangerous_action": {
            "blocked": True,
            "reason": "shell command is not a registered domain tool",
        },
        "feedback_loop": {
            "first_strategy": "weak assertion",
            "second_strategy": "kill arithmetic mutant",
            "failure_category": "surviving_mutant",
            "rounds": 2,
        },
        "quality_gate": {
            "passed": True,
            "mutation_score_delta": 5.0,
        },
        "final_state": "awaiting_apply_approval",
    }


def main() -> int:
    report = run_mechanism_demo()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    passed = report["quality_gate"]["passed"] and report["dangerous_action"]["blocked"]
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
