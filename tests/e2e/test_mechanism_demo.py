"""E2E test for mechanism demo — deterministic, offline, byte-stable."""

import json
import sys
from io import StringIO

import pytest

from scripts.mechanism_demo import main, run_mechanism_demo


def test_demo_reports_all_required_mechanisms() -> None:
    """Demo must report dangerous_action, feedback_loop, quality_gate, final_state."""
    report = run_mechanism_demo()
    assert report["dangerous_action"]["blocked"] is True
    assert report["feedback_loop"]["first_strategy"] == "weak assertion"
    assert report["feedback_loop"]["second_strategy"] == "kill arithmetic mutant"
    assert report["quality_gate"]["passed"] is True
    assert report["final_state"] == "awaiting_apply_approval"


def test_demo_is_deterministic() -> None:
    """Two runs must produce identical output."""
    first = run_mechanism_demo()
    second = run_mechanism_demo()
    assert first == second


def test_main_exit_zero() -> None:
    """main() must return 0 when all mechanisms pass."""
    assert main() == 0
