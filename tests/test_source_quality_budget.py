"""R10-06: a source-debt inventory must not silently forgive new debt."""

import importlib.util
from pathlib import Path

import pytest


_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "quality"
    / "source_quality_budget.py"
)
_SPEC = importlib.util.spec_from_file_location("source_quality_budget", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(module)


def test_counts_function_imports_and_error_suppression(tmp_path):
    source = tmp_path / "sample.py"
    source.write_text(
        """import os
def f():
    import json
    from pathlib import Path
    try:
        raise ValueError()
    except Exception:
        pass
async def g():
    try:
        pass
    except:
        pass
""",
        encoding="utf-8",
    )
    report = module.inventory(tmp_path)
    assert report["files_scanned"] == 1
    assert report["totals"] == {
        "imports_in_functions": 2,
        "broad_except": 1,
        "bare_except": 1,
        "silent_except": 2,
    }


def test_baseline_fails_when_any_metric_grows(tmp_path):
    (tmp_path / "a.py").write_text(
        "def f():\n    import os\n", encoding="utf-8"
    )
    current = module.inventory(tmp_path)
    baseline = {
        "schema_version": 1,
        "totals": {key: 0 for key in module.METRICS},
    }
    errors = module.compare_to_baseline(current, baseline)
    assert any("imports_in_functions" in error for error in errors)
    baseline["totals"]["imports_in_functions"] = 1
    assert module.compare_to_baseline(current, baseline) == []


def test_bad_baseline_is_not_treated_as_success(tmp_path):
    (tmp_path / "empty.py").write_text("pass\n", encoding="utf-8")
    current = module.inventory(tmp_path)
    with pytest.raises(ValueError, match="schema"):
        module.compare_to_baseline(current, {"schema_version": 2})
    with pytest.raises(ValueError, match="Missing valid baseline"):
        module.compare_to_baseline(current, {"schema_version": 1, "totals": {}})
