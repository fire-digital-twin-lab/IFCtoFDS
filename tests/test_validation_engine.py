import os
from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.geometry.engine import process_model_geometry
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.validation.acceptance import AcceptanceStatus
from ifc_to_fds.validation.engine import run_independent_validation

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_validation_engine_verified():
    fzk_path = os.path.join(REPO_ROOT, "examples", "AC20-FZK-Haus.ifc")
    model, ifc_file = extract_inventory(fzk_path)
    model = process_model_geometry(model, ifc_file)
    fds_text, _ = serialize_fds(model, cell_size=0.2, force_all_geom=True)

    report = run_independent_validation(model, fds_text)

    # Acceptance verdict must be VERIFIED
    assert report.status == AcceptanceStatus.VERIFIED
    assert report.summary.get("P0", 0) == 0
    assert report.summary.get("P1", 0) == 0
    assert report.matched_count == 82
    assert report.missing_count == 0


def test_validation_engine_mutation_rejection():
    fzk_path = os.path.join(REPO_ROOT, "examples", "AC20-FZK-Haus.ifc")
    model, ifc_file = extract_inventory(fzk_path)
    model = process_model_geometry(model, ifc_file)
    fds_text, _ = serialize_fds(model, cell_size=0.2, force_all_geom=True)

    # Mutate FDS text: maliciously or accidentally delete the external wall
    # GlobalId: 3rPX_Juz59peXXY6wDJl18
    mutated_lines = []
    skip = False
    for line in fds_text.splitlines():
        if "3rPX_Juz59peXXY6wDJl18" in line:
            skip = True
            continue
        if skip and line.startswith("&GEOM"):
            skip = False
            continue
        if not skip:
            mutated_lines.append(line)
    mutated_fds_text = "\n".join(mutated_lines)

    report = run_independent_validation(model, mutated_fds_text)

    # Acceptance gate MUST reject the corrupted simulation input
    assert report.status == AcceptanceStatus.REJECTED
    assert report.summary.get("P0", 0) > 0
    assert report.missing_count > 0

    # Verify that the specific missing wall is reported in findings
    p0_findings = [f for f in report.findings if f.severity == "P0"]
    assert any("3rPX_Juz59peXXY6wDJl18" in f.detail for f in p0_findings)
