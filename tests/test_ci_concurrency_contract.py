"""Regression: push and pull_request checks may not cancel each other.

Required check names overlap between the two event types; cross-event
cancellation leaves branch protection in 'cancelled/expected' even if
the other event's run passed.
"""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/quality.yml",
        ".github/workflows/verified.yml",
    ],
)
def test_workflow_concurrency_distinguishes_push_and_pull_request(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    group = next(line for line in text.splitlines() if line.strip().startswith("group:"))
    assert "github.workflow" in group
    assert "github.event_name" in group
    assert "github.head_ref || github.ref_name" in group
    assert "cancel-in-progress: true" in text
    assert "pull_request:" in text and "push:" in text
