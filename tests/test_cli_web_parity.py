"""The CLI and the web API give the same deck and verdict for the same IFC (plan M5.5)."""

import json
import runpy
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow  # starts a CLI process and a server process

TINY = Path(__file__).parent / "baseline" / "fixtures" / "tiny.ifc"


def test_tiny_model_gives_identical_decks(tmp_path_factory):
    work = tmp_path_factory.mktemp("p")  # short root: artifact paths stay under Windows MAX_PATH
    script = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "cli-web-deck-parity.py"))
    evidence = work / "evidence.json"
    assert script["main"](["--ifc", str(TINY), "--work", str(work / "w"), "--evidence", str(evidence)]) == 0
    data = json.loads(evidence.read_text())
    assert data["identical"] and data["cli"]["sha256"] == data["web"]["sha256"]
    assert data["web"]["state"] == "COMPLETED" and data["web"]["verdict"] == "MAPPING_VERIFIED"
