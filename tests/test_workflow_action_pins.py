"""Every external GitHub Action is pinned to a full commit SHA (a tag can be moved after review)."""

import re
from pathlib import Path

WORKFLOWS = sorted((Path(__file__).parents[1] / ".github" / "workflows").glob("*.yml"))


def test_every_external_action_is_pinned_to_a_full_commit_sha():
    unpinned = [
        f"{workflow.name}: {ref}"
        for workflow in WORKFLOWS
        for ref in re.findall(r"uses:\s*(\S+)", workflow.read_text(encoding="utf-8"))
        if not ref.startswith("./") and not re.fullmatch(r".+@[0-9a-f]{40}", ref)
    ]
    assert WORKFLOWS and not unpinned, unpinned
