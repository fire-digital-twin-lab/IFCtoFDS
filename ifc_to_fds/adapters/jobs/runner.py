"""Worker execution runner calling application use cases."""

import json
from pathlib import Path
from typing import Any


class WorkerRunner:
    """Executes background jobs by invoking application use cases."""

    @staticmethod
    def run(directory: str | Path) -> int:
        from ifc_to_fds.diagnostics import execution_scope

        with execution_scope(directory):
            return WorkerRunner.execute(directory)

    @staticmethod
    def execute(directory: str | Path) -> int:
        directory = Path(directory)
        job_id = directory.name
        try:
            request = json.loads(
                (directory / "request.json").read_text(encoding="utf-8")
            )
            job_id = request.get("job_id", job_id)
            if request.get("mode") == "preview":
                from ifc_to_fds.application.use_cases.preview_model import preview_model

                result = preview_model(request["paths"], directory)
            elif request.get("mode") == "inventory":
                from ifc_to_fds.core.inventory import extract_inventory

                models = [extract_inventory(path)[0] for path in request["paths"]]
                result: dict[str, Any] = dict(
                    total_elements=sum(len(m.elements) for m in models),
                    storeys=[s.name for m in models for s in m.storey_references],
                    storey_references=[
                        s.model_dump() for m in models for s in m.storey_references
                    ],
                    sources=[m.source.model_dump() for m in models],
                )
            elif request.get("mode") == "scenario":
                import hashlib
                from ifc_to_fds.fire.mesh_gate import check_mesh_resolution
                from ifc_to_fds.fire.scenario_emitter import emit_fire_scenario
                from ifc_to_fds.domain.mapping import MappingPlan

                scenario_payload = request.get("configuration") or {}
                if not scenario_payload and (directory / "scenario.json").is_file():
                    try:
                        scenario_payload = json.loads(
                            (directory / "scenario.json").read_text(encoding="utf-8")
                        )
                    except Exception:
                        scenario_payload = {}
                scenario_input = (
                    scenario_payload.get("scenario_data")
                    if isinstance(scenario_payload, dict) and "scenario_data" in scenario_payload
                    else scenario_payload
                )
                cell_size = (
                    scenario_payload.get("cell_size", 0.2)
                    if isinstance(scenario_payload, dict)
                    else 0.2
                )
                mesh_gate = check_mesh_resolution(scenario_input, cell_size=cell_size)

                peak_hrr_mw = 0.0
                if isinstance(scenario_input, dict):
                    peak_hrr_mw = (
                        scenario_input.get("total_peak_hrr_mw")
                        or scenario_input.get("peak_hrr_mw")
                        or 0.0
                    )
                elif hasattr(scenario_input, "total_peak_hrr_mw"):
                    peak_hrr_mw = scenario_input.total_peak_hrr_mw
                if not peak_hrr_mw and isinstance(scenario_payload, dict):
                    peak_hrr_mw = (
                        scenario_payload.get("total_peak_hrr_mw")
                        or scenario_payload.get("peak_hrr_mw")
                        or 0.0
                    )
                if not peak_hrr_mw and mesh_gate.evidence:
                    peak_hrr_mw = (mesh_gate.evidence.get("peak_hrr_kw") or 0.0) / 1000.0

                # Extract scenario emitter parameters
                bundle_sha = ""
                ev_selections = []
                opening_states = None
                devices = None
                if isinstance(scenario_input, dict):
                    bundle_sha = scenario_input.get("bundle_sha256") or ""
                    ev_selections = scenario_input.get("ev_selections") or []
                    opening_states = scenario_input.get("opening_states")
                    devices = scenario_input.get("devices")
                if not bundle_sha and isinstance(scenario_payload, dict):
                    bundle_sha = scenario_payload.get("bundle_sha256") or ""
                if not ev_selections and isinstance(scenario_payload, dict):
                    ev_selections = scenario_payload.get("ev_selections") or []
                if not opening_states and isinstance(scenario_payload, dict):
                    opening_states = scenario_payload.get("opening_states")
                if not devices and isinstance(scenario_payload, dict):
                    devices = scenario_payload.get("devices")

                # Locate base FDS or mapping plan if available
                base_fds_text = ""
                mapping_plan = MappingPlan(cell_size=cell_size)
                if (directory / "model.fds").is_file():
                    base_fds_text = (directory / "model.fds").read_text(encoding="utf-8")
                    if (directory / "model_manifest.json").is_file():
                        try:
                            m_raw = json.loads((directory / "model_manifest.json").read_text(encoding="utf-8"))
                            if "mapping_plan" in m_raw:
                                mapping_plan = MappingPlan.model_validate(m_raw["mapping_plan"])
                        except Exception:
                            pass
                elif bundle_sha and directory.parent.is_dir():
                    try:
                        siblings = list(directory.parent.iterdir())
                    except OSError:
                        siblings = []
                    for sib in siblings:
                        if sib != directory and sib.is_dir() and (sib / "model_manifest.json").is_file():
                            try:
                                m_raw = json.loads((sib / "model_manifest.json").read_text(encoding="utf-8"))
                                if m_raw.get("bundle_sha256") == bundle_sha:
                                    if (sib / "model.fds").is_file():
                                        base_fds_text = (sib / "model.fds").read_text(encoding="utf-8")
                                    if (sib / "mapping_plan.json").is_file():
                                        mapping_plan = MappingPlan.model_validate_json(
                                            (sib / "mapping_plan.json").read_text(encoding="utf-8")
                                        )
                                    elif "mapping_plan" in m_raw:
                                        mapping_plan = MappingPlan.model_validate(m_raw["mapping_plan"])
                                    break
                            except Exception:
                                continue

                if not base_fds_text:
                    base_chid = f"ev_base_{bundle_sha[:8]}" if bundle_sha else "ev_base"
                    base_fds_text = (
                        f"&HEAD CHID='{base_chid}', TITLE='EV Fire Simulation' /\n"
                        f"&TIME T_END=1800.0 /\n"
                        f"&MESH IJK=50,50,20, XB=0,10,0,10,0,4 /\n"
                        f"&TAIL /\n"
                    )

                evidence_dict = dict(mesh_gate.evidence) if mesh_gate.evidence else {}
                bundle = None
                if ev_selections:
                    bundle = emit_fire_scenario(
                        mapping_plan=mapping_plan,
                        bundle_sha256=bundle_sha or ("a" * 64),
                        ev_selections=ev_selections,
                        opening_states=opening_states,
                        devices=devices,
                        verification_status="MAPPING_VERIFIED",
                    )
                    # Splice into scenario.fds
                    if "&TAIL /" in base_fds_text:
                        scenario_fds_text = base_fds_text.replace(
                            "&TAIL /",
                            bundle.fds_fragment + "\n&TAIL /\n",
                        )
                    else:
                        scenario_fds_text = base_fds_text + "\n" + bundle.fds_fragment + "\n&TAIL /\n"

                    # Update &TIME T_END so FDS simulation runs the full fire duration
                    # Preserve longer T_END if already configured
                    import re
                    m_tend = re.search(r"&TIME\s+[^/]*?T_END\s*=\s*([\d.]+)", scenario_fds_text)
                    curr_tend = float(m_tend.group(1)) if m_tend else 0.0
                    target_tend = max(curr_tend, 1800.0)
                    if isinstance(scenario_input, dict) and "t_end_s" in scenario_input:
                        try:
                            target_tend = max(target_tend, float(scenario_input["t_end_s"]))
                        except (ValueError, TypeError):
                            pass

                    if m_tend:
                        scenario_fds_text = re.sub(
                            r"(&TIME\s+[^/]*?T_END\s*=\s*)[\d.]+",
                            r"\g<1>" + f"{target_tend:.1f}",
                            scenario_fds_text,
                        )
                    else:
                        scenario_fds_text = re.sub(
                            r"(&HEAD[^\n]*\n)",
                            r"\1&TIME T_END=" + f"{target_tend:.1f}" + " /\n",
                            scenario_fds_text,
                        )

                    (directory / "scenario.fds").write_text(scenario_fds_text, encoding="utf-8")

                    evidence_dict["scenario_id"] = bundle.scenario_id
                    evidence_dict["bundle_sha256"] = bundle.bundle_sha256
                    evidence_dict["ev_evaluations"] = [
                        ev.model_dump() if hasattr(ev, "model_dump") else ev
                        for ev in bundle.ev_selections
                    ]

                from ifc_to_fds.results import ARTIFACTS
                available_artifacts = {
                    k: dict(filename=v)
                    for k, v in ARTIFACTS.items()
                    if (directory / v).is_file()
                }
                result = {
                    "status": "COMPLETED",
                    "verdict": mesh_gate.status.value,
                    "mesh_status": mesh_gate.status.value,
                    "peak_hrr_mw": float(peak_hrr_mw),
                    "evidence": evidence_dict,
                    "artifacts": available_artifacts,
                }
                if bundle:
                    result["scenario_id"] = bundle.scenario_id
                    result["bundle_sha256"] = bundle.bundle_sha256
                    result["fds_file"] = "scenario.fds"
            else:
                from ifc_to_fds.pipeline import convert, save_artifacts

                result = convert(
                    request["paths"], request["configuration"], str(directory)
                )
                save_artifacts(result, directory / "model.fds")
                from ifc_to_fds.results import public_result

                result = public_result(result, directory=directory)
            if request.get("mode") == "inventory":
                from ifc_to_fds.results import research_context

                result["research"] = research_context(result["sources"], {})
            (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")
            return 0
        except Exception as exc:
            from ifc_to_fds.diagnostics import failure_diagnostic

            diagnostic = failure_diagnostic(exc, job_id)
            (directory / "diagnostics.json").write_text(
                json.dumps(diagnostic), encoding="utf-8"
            )
            (directory / "error.txt").write_text(
                f"{type(exc).__name__}: {exc}", encoding="utf-8"
            )
            return 1
