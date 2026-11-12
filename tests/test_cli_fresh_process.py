"""Hồi quy cho các điểm vào chạy trong tiến trình Python mới."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/baseline/fixtures/tiny.ifc"


def run_entry_point(tmp_path, module, *args):
    env = {
        **os.environ,
        "IFCFDS_GEOMETRY_CACHE": str(tmp_path / "geometry-cache"),
        "IFCFDS_SOLVER_AUTODISCOVERY": "0",
    }
    return subprocess.run(
        [sys.executable, "-m", module, *(str(arg) for arg in args)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_convert_and_audit_from_fresh_processes(tmp_path):
    fds = tmp_path / "room.fds"
    manifest = tmp_path / "room_manifest.json"
    converted = run_entry_point(tmp_path, "ifc_to_fds", "convert", SOURCE, "-o", fds)
    assert converted.returncode == 0, converted.stdout + converted.stderr
    assert "MAPPING_VERIFIED" in converted.stdout
    evidence = read_json(manifest)
    assert evidence["output_complete"] is True
    assert evidence["fds_sha256"] == hashlib.sha256(fds.read_bytes()).hexdigest()

    report = tmp_path / "independent.json"
    audited = run_entry_point(
        tmp_path, "ifc_to_fds", "audit", SOURCE, "--fds", fds,
        "--manifest", manifest, "-o", report,
    )
    assert audited.returncode == 0, audited.stdout + audited.stderr
    evidence = read_json(report)
    assert evidence["mapping_status"] == "MAPPING_VERIFIED"
    assert evidence["gates"]["source_inventory"]["status"] == "PASS"


def test_worker_from_fresh_process_seals_verified_mapping(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "request.json").write_text(
        json.dumps({"mode": "convert", "paths": [str(SOURCE)], "configuration": {}}),
        encoding="utf-8",
    )

    worked = run_entry_point(tmp_path, "ifc_to_fds.jobs", job)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    result = read_json(job / "result.json")
    checkpoint = read_json(job / "audit-state.json")
    assert result["mapping_status"] == "MAPPING_VERIFIED"
    assert checkpoint["checkpoint_status"] == "VERIFIED_SEALED"
    assert checkpoint["bundle_sha256"] == read_json(job / "model_manifest.json")["bundle_sha256"]
