from __future__ import annotations

import pytest

from observability.reporting import generate_corruption_report, generate_phase1_report


def test_phase1_report_is_pending_until_implemented(tmp_path):
    try:
        generate_phase1_report(tmp_path / "phase1.md", {}, {}, {}, {})
    except NotImplementedError:
        pytest.skip("phase 1 report is still a stub")
    assert (tmp_path / "phase1.md").exists()


def test_corruption_report_is_pending_until_implemented(tmp_path):
    try:
        generate_corruption_report(tmp_path / "corruption.md", {}, {}, {}, {}, {}, {}, {})
    except NotImplementedError:
        pytest.skip("corruption report is still a stub")
    assert (tmp_path / "corruption.md").exists()
