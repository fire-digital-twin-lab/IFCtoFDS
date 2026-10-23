"""The reviewed diagnostic change cannot silently alter acceptance baselines."""

import hashlib
import json
from pathlib import Path

from .generate_baseline import SNAPSHOT_DIR


def test_only_reviewed_source_operand_labels_changed():
    ledger = json.loads(Path(__file__).with_name("diagnostic_changes.json").read_text())
    raw = (SNAPSHOT_DIR / ledger["snapshot"]).read_text(encoding="utf-8")
    assert hashlib.sha256(raw.encode()).hexdigest() == ledger["after_sha256"]
    data = json.loads(raw)
    assert len(ledger["changes"]) == 28
    for change in ledger["changes"]:
        finding = data["findings"][change["index"]]
        assert finding["element_id"] == change["entity_key"]
        assert finding["title"] == change["after"]
        assert change["after"] == change["before"].replace(
            "Invalid saved ", "Invalid source ", 1
        )
    previous = raw.replace("Invalid source ", "Invalid saved ")
    assert hashlib.sha256(previous.encode()).hexdigest() == ledger["before_sha256"]
