"""Test path setup plus shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
for path in (str(ROOT), str(TESTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture
def panel_args():
    return {
        "topic": "Should the DC add a second packing station?",
        "seats": [
            {"name": "associate", "brief": "You pack boxes every shift."},
            {"name": "supervisor", "brief": "You own the shift plan."},
        ],
    }


@pytest.fixture
def valid_panel():
    return {
        "seat_reports": [
            {"seat": "associate", "model": "fake/fake-model", "findings": "Flow binds."},
            {"seat": "supervisor", "model": "fake/fake-model", "findings": "Payback is 2 seasons."},
        ],
        "synthesis": "Add the station only with handoff fixes.",
        "contradictions": [],
        "unresolved": [],
    }
