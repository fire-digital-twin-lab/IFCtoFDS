import json

import pytest

from scripts.prepare_verification_matrix import prepare_matrix


def test_preparing_solver_cases_never_attests_ifc_mapping_or_editor_import(tmp_path):
    result = prepare_matrix(tmp_path / "matrix", ["obst", "geom_multi_surface"])
    assert result["status"] == "INCONCLUSIVE"
    assert result["pyrosim_execution"] == "NOT_RUN"
    for case in result["cases"].values():
        assert case["gates"]["syntax"] == "PASS"
        assert case["gates"]["mapping"] == "NOT_RUN"
        assert case["gates"]["verification"] != "PASS"
        report = json.loads((tmp_path / "matrix" / case["packet"]).read_text(encoding="utf-8"))
        assert report["capabilities"]["geom_cut_cells"]["supported"] is False
        template = json.loads((tmp_path / "matrix" / case["packet"]).with_name("import-evidence.template.json").read_text())
        assert template["import_result"] == "PENDING"
        assert template["source_sha256"] == case["source_sha256"]


def test_existing_matrix_directory_is_protected(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError):
        prepare_matrix(output, ["obst"])


def test_empty_acceptance_matrix_cannot_pass(tmp_path):
    with pytest.raises(ValueError, match="at least one"):
        prepare_matrix(tmp_path / "empty", [])
