"""R10-02 contract tests for dependency injection and behavior preservation."""
import json
import pytest
from ifc_to_fds.adapters.conversion import DefaultMappingPlanner, DefaultFdsSerializer, DefaultGeometryPackageWriter
from ifc_to_fds.application.ports.conversion import ModelPreparerPort, MappingPlannerPort, VerifiedFdsSerializerPort, GeometryPackageWriterPort
from ifc_to_fds.application.use_cases.convert_verified import ConvertVerifiedUseCase
from ifc_to_fds.bootstrap.container import create_container
from ifc_to_fds.domain.mapping import build_mapping_plan
from ifc_to_fds.geometry.storage import write_package
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mep.network import build_hvac_network
from ifc_to_fds.pipeline import convert


def test_container_wires_ports_and_legacy_constructor():
    use_case = create_container().get_convert_verified_use_case()
    assert isinstance(use_case.model_preparer, ModelPreparerPort)
    assert isinstance(use_case.mapping_planner, MappingPlannerPort)
    assert isinstance(use_case.fds_serializer, VerifiedFdsSerializerPort)
    assert isinstance(use_case.geometry_writer, GeometryPackageWriterPort)
    assert use_case.audit_use_case is not None
    assert ConvertVerifiedUseCase().model_preparer is None


def test_default_adapter_mapping_serialization_parity(box_model):
    original = box_model.model_copy(deep=True)
    actual = box_model.model_copy(deep=True)
    expected_plan = build_mapping_plan(original, cell_size=0.5, hvac_network=build_hvac_network(original))
    actual_plan = DefaultMappingPlanner().plan(actual, cell_size=0.5)
    assert expected_plan.model_dump(mode="json") == actual_plan.model_dump(mode="json")
    expected_text, expected_manifest = serialize_fds(original, cell_size=0.5, mapping_plan=expected_plan)
    actual_text, actual_manifest = DefaultFdsSerializer().serialize(actual, cell_size=0.5, mapping_plan=actual_plan)
    assert expected_text.encode("utf-8") == actual_text.encode("utf-8")
    assert expected_manifest.model_dump(mode="json") == actual_manifest.model_dump(mode="json")


def test_geometry_package_writer_uses_identical_format(box_model, tmp_path):
    expected = write_package(box_model.model_copy(deep=True), tmp_path / "legacy.json", None)
    actual = DefaultGeometryPackageWriter().write(box_model.model_copy(deep=True), tmp_path / "new.json", None)
    assert expected["sha256"] == actual["sha256"]


def test_injected_port_order_and_audit_not_run_checkpoint(box_model, tmp_path):
    calls = []
    class Prepare:
        def prepare(self, paths, configuration):
            calls.append("prepare")
            return box_model.model_copy(deep=True)
    class Plan:
        def plan(self, model, *, cell_size):
            calls.append("plan")
            return DefaultMappingPlanner().plan(model, cell_size=cell_size)
    class Serialize:
        def serialize(self, model, *, cell_size, mapping_plan):
            calls.append("serialize")
            return DefaultFdsSerializer().serialize(model, cell_size=cell_size, mapping_plan=mapping_plan)
    class Package:
        def write(self, model, path, owner):
            calls.append("package")
            return DefaultGeometryPackageWriter().write(model, path, owner)
    class Audit:
        def execute(self, paths, fds_text, manifest, configuration, geometry_package):
            calls.append("audit")
            state = json.loads((tmp_path / "audit-state.json").read_text("utf-8"))
            assert state["status"] == "NOT_RUN"
            assert state["checkpoint_status"] == "DRAFT_NOT_SEALED"
            raise RuntimeError("audit boundary")
    use_case = ConvertVerifiedUseCase(audit_use_case=Audit(), model_preparer=Prepare(), mapping_planner=Plan(), fds_serializer=Serialize(), geometry_writer=Package())
    with pytest.raises(RuntimeError, match="audit boundary"):
        use_case.execute(["unused.ifc"], {"cell_size": 0.5}, tmp_path)
    assert calls == ["prepare", "plan", "serialize", "package", "audit"]


def test_pipeline_delegates_to_composition_root(monkeypatch, tmp_path):
    calls = []
    class UseCase:
        def execute(self, paths, configuration, output_directory):
            calls.append((paths, configuration, output_directory))
            return {"injected": True}
    class Container:
        def get_convert_verified_use_case(self):
            return UseCase()
    monkeypatch.setattr("ifc_to_fds.bootstrap.container.create_container", lambda: Container())
    assert convert(["sample.ifc"], {"cell_size": 0.25}, tmp_path) == {"injected": True}
    assert calls == [(["sample.ifc"], {"cell_size": 0.25}, tmp_path)]
