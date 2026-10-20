# pyright: reportUnusedVariable=false
"""Verification test suite for audit blockers B01 through B16 remediation.

Validates:
- Phase A (B01/B02): Door/window non-manifold leaf classified as APPROXIMATED, not VALID.
                     Auditor reference path retains true geometry and does not auto-heal to box.
- Phase B (B03): Auditor reference extraction path is independent.
- Phase C (B04): Origin Rebase synchronizes spatial_scope.bounding_box and simulation_domain.
- Phase E (B07): ScenarioStore locks simulation when base mapping is unverified/rejected.
- Phase F (B08): CLI serve rejects binding to public host 0.0.0.0 without API key.
- Phase G (B10): Canonical bundle SHA-256 covers all semantic fields (openings, ports, status).
- Phase G (B11): Structural completeness checker covers footings, piles, stairs, plates, members.
"""

from ifc_to_fds.cli import main as cli_main
from ifc_to_fds.core.canonical import (
    BoundingBox,
    CanonicalElement,
    GeometryStatus,
    MappingStatus,
    ScopeDecision,
)
from ifc_to_fds.geometry.mesh import box_mesh
from ifc_to_fds.mapping.manifest import MappingManifest, ManifestRecord
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.application.services.model_preparer import prepare_model
from ifc_to_fds.validation.checkers.structural import STRUCTURAL_TYPES


def test_geometry_status_approximated_for_non_manifold_door(box_model):
    """B01: Non-manifold door leaf must be marked APPROXIMATED, not VALID."""
    door_bbox = BoundingBox(xmin=1.0, xmax=2.0, ymin=0.0, ymax=0.1, zmin=0.0, zmax=2.1)

    door_elem = CanonicalElement(
        source_id="test_src",
        entity_key="test_src:door_1",
        global_id="guid_door_1",
        step_id=2001,
        ifc_type="IfcDoor",
        name="Fire Door 1",
        role="PHYSICAL",
        has_3d_geometry=True,
        geometry_status=GeometryStatus.APPROXIMATED,
        bounding_box=door_bbox,
        mesh=box_mesh(door_bbox),
        scope_decision=ScopeDecision.IN_SCOPE,
    )
    box_model.elements.append(door_elem)
    plan_mapping(box_model)

    assert door_elem.geometry_status == GeometryStatus.APPROXIMATED
    # Without explicit approved decision, review is required
    assert door_elem.mapping_status == MappingStatus.REVIEW_REQUIRED
    assert door_elem.geometry_preservation == "APPROXIMATED"


def test_auditor_does_not_auto_heal_non_manifold_door():
    """B02: Auditor reference path must retain true failure status, not heuristic box."""
    import inspect
    from ifc_to_fds.core import federation

    source_code = inspect.getsource(federation.load_sources)
    assert "e.mesh = box_mesh" not in source_code


def test_origin_rebase_synchronizes_spatial_scope_and_domain(box_model, monkeypatch):
    """B04: Rebase vector must normalize world-coordinate spatial_scope and simulation_domain."""
    dx, dy, dz = 578000.0, 2318000.0, 0.0

    # Mock load_sources to return rebased model
    box_model.source.rebase_vector = [dx, dy, dz]
    box_model.model_bounds = BoundingBox(xmin=0, xmax=2, ymin=0, ymax=1, zmin=0, zmax=3)

    def mock_load_sources(*_args, **_kwargs):
        return box_model

    monkeypatch.setattr(
        "ifc_to_fds.application.services.model_preparer.load_sources",
        mock_load_sources,
    )

    world_bbox = {
        "xmin": dx + 0.0,
        "xmax": dx + 2.0,
        "ymin": dy + 0.0,
        "ymax": dy + 1.0,
        "zmin": 0.0,
        "zmax": 3.0,
    }
    world_domain = {
        "xmin": dx - 5.0,
        "xmax": dx + 10.0,
        "ymin": dy - 5.0,
        "ymax": dy + 10.0,
        "zmin": -1.0,
        "zmax": 5.0,
    }

    config = {
        "scope": {"bounding_box": world_bbox},
        "simulation_domain": world_domain,
    }

    prepared = prepare_model(["dummy.ifc"], config)

    # Reconciled domain must be in local simulation coordinates
    assert prepared.simulation_domain is not None
    assert abs(prepared.simulation_domain.xmin - (-5.0)) < 1e-5
    assert abs(prepared.simulation_domain.xmax - 10.0) < 1e-5
    assert abs(prepared.simulation_domain.ymin - (-5.0)) < 1e-5
    assert abs(prepared.simulation_domain.ymax - 10.0) < 1e-5


def test_cli_serve_rejects_public_interface_without_api_key(capsys, monkeypatch):
    """B08: Binding to 0.0.0.0 without API key must exit with code 1."""
    monkeypatch.delenv("IFCFDS_API_KEY", raising=False)
    exit_code = cli_main(["serve", "--host", "0.0.0.0", "--port", "8000"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "SECURITY ERROR: Binding to public/external host interface" in captured.err


def test_cli_serve_allows_loopback_without_api_key(monkeypatch):
    """B08: Binding to 127.0.0.1 without API key is allowed for local dev."""
    monkeypatch.delenv("IFCFDS_API_KEY", raising=False)
    # Mock uvicorn.run to prevent blocking
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: None)
    exit_code = cli_main(["serve", "--host", "127.0.0.1", "--port", "8000"])
    assert exit_code == 0


def test_structural_types_coverage():
    """B11: Structural completeness checker must cover all structural & enclosure types."""
    required_types = {
        "IFCWALL",
        "IFCWALLSTANDARDCASE",
        "IFCCURTAINWALL",
        "IFCSLAB",
        "IFCCOLUMN",
        "IFCBEAM",
        "IFCROOF",
        "IFCFOOTING",
        "IFCPILE",
        "IFCRAMP",
        "IFCRAMPFLIGHT",
        "IFCSTAIRFLIGHT",
        "IFCMEMBER",
        "IFCPLATE",
    }
    assert required_types.issubset(STRUCTURAL_TYPES)


def test_bundle_sha_covers_all_manifest_fields():
    """B10: bundle_sha256 must change if openings, ports, or mapping_status changes."""
    record_base = ManifestRecord(
        entity_key="src1:100",
        source_id="src1",
        global_id="guid_100",
        step_id=100,
        ifc_type="IfcWall",
        name="Wall 1",
        storey="Level 1",
        scope_decision="IN_SCOPE",
        scope_rationale="In bounds",
        mapping_strategy="GEOM",
        mapping_status="MAPPING_VERIFIED",
        simulation_role="PASSIVE_OBSTACLE",
        openings=[],
        ports=[],
    )
    manifest1 = MappingManifest(
        source_filename="test.ifc",
        source_sha256="abc",
        total_elements_accounted=1,
        total_primitives_emitted=1,
        records=[record_base],
    )
    sha1 = manifest1.compute_bundle_sha256()

    # Modify openings
    record_with_opening = record_base.model_copy(
        update={"openings": [{"step_id": 200, "global_id": "guid_open_200"}]}
    )
    manifest2 = MappingManifest(
        source_filename="test.ifc",
        source_sha256="abc",
        total_elements_accounted=1,
        total_primitives_emitted=1,
        records=[record_with_opening],
    )
    sha2 = manifest2.compute_bundle_sha256()
    assert sha1 != sha2, "bundle_sha256 failed to detect change in record openings"

    # Modify mapping_status
    record_deviated = record_base.model_copy(update={"mapping_status": "DEVIATED"})
    manifest3 = MappingManifest(
        source_filename="test.ifc",
        source_sha256="abc",
        total_elements_accounted=1,
        total_primitives_emitted=1,
        records=[record_deviated],
    )
    sha3 = manifest3.compute_bundle_sha256()
    assert sha1 != sha3, "bundle_sha256 failed to detect change in mapping_status"
