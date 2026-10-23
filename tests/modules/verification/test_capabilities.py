from ifc_to_fds.modules.verification.api import verification_capabilities, summarize_handoff
from ifc_to_fds.modules.verification.application.effective_obstructions import effective_obstructions
from tests.support.solver_cases import solver_cases


def test_declared_geom_surface_support_cannot_grant_effective_geometry_pass():
    scope = verification_capabilities()
    assert scope["geom_surfaces"]["supported"]
    assert not scope["geom_cut_cells"]["supported"]
    gate = effective_obstructions(solver_cases()["geom"], "")
    assert gate.status == "INCONCLUSIVE"
    assert summarize_handoff({"capabilities": scope})[1]["status"] != "PASS"


def test_declared_editor_capability_requires_manual_evidence():
    scope = verification_capabilities()
    assert scope["editor_import"]["gui_automated"] is False
    assert scope["simulation_physics"] == "NOT_VERIFIED"
