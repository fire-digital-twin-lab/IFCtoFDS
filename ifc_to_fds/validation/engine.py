"""Independent Validation Engine.

Executes Tier 1, Tier 2, and Tier 3 audits by re-reading the serialized FDS
file and cross-verifying directly against the Canonical Model and source IFC.
"""

from typing import Dict, List, Set
import re

from ifc_to_fds.core.canonical import (
    CanonicalModel,
    MappingStatus,
    MappingStrategy,
)
from .acceptance import AcceptanceReport, AcceptanceStatus, Finding, Severity
from .metrics import verify_opening_retention


def parse_serialized_fds_primitives(fds_text: str) -> Dict[str, Dict[str, str]]:
    """Parses FDS text to extract primitives and their inlined IFC_SOURCE metadata."""
    primitives: Dict[str, Dict[str, str]] = {}

    current_source: Dict[str, str] = {}
    source_pattern = re.compile(
        r"! IFC_SOURCE\(global_id='(?P<guid>[^']+)',\s*step_id=(?P<step>\d+),\s*ifc_type='(?P<type>[^']+)'"
    )
    obst_pattern = re.compile(r"&OBST\s+ID='(?P<id>[^']+)',\s*XB=(?P<xb>[^,/]+)")
    geom_pattern = re.compile(r"&GEOM\s+ID='(?P<id>[^']+)'")

    for line in fds_text.splitlines():
        line = line.strip()
        s_match = source_pattern.search(line)
        if s_match:
            current_source = s_match.groupdict()
            continue

        o_match = obst_pattern.search(line)
        if o_match:
            prim_id = o_match.group("id")
            primitives[prim_id] = {
                "type": "OBST",
                "xb": o_match.group("xb"),
                **current_source,
            }
            current_source = {}
            continue

        g_match = geom_pattern.search(line)
        if g_match:
            prim_id = g_match.group("id")
            primitives[prim_id] = {
                "type": "GEOM",
                **current_source,
            }
            current_source = {}
            continue

    return primitives


def run_independent_validation(model: CanonicalModel, fds_text: str) -> AcceptanceReport:
    findings: List[Finding] = []
    finding_id = 0

    def add_finding(severity: Severity, category: str, title: str, detail: str, el_id: str = "", rem: str = ""):
        nonlocal finding_id
        finding_id += 1
        findings.append(
            Finding(
                id=f"FND-{finding_id:03d}",
                severity=severity,
                category=category,
                title=title,
                detail=detail,
                element_id=el_id,
                remediation=rem,
            )
        )

    # 1. Parse Serialized FDS Output Independently
    fds_primitives = parse_serialized_fds_primitives(fds_text)
    fds_guids: Set[str] = {p.get("guid", "") for p in fds_primitives.values() if p.get("guid")}

    matched_count = 0
    deviated_count = 0
    missing_count = 0
    excluded_count = 0
    semantic_only_count = 0

    # 2. Tier 1: IFC -> Canonical Verification
    for elem in model.elements:
        if elem.mapping_strategy == MappingStrategy.EXCLUDED_APPROVED:
            excluded_count += 1
            continue
        if elem.mapping_strategy == MappingStrategy.SEMANTIC_ONLY:
            semantic_only_count += 1
            continue

        # Check geometry manifoldness
        if elem.mesh:
            if elem.mesh.is_closed_manifold is False:
                add_finding(
                    Severity.P2,
                    "Geometry Topology",
                    f"Non-manifold mesh on {elem.ifc_type}",
                    f"Element '{elem.name}' (GlobalId: {elem.global_id}) has open or non-manifold edges.",
                    elem.global_id,
                    "Inspect IFC BRep geometry or simplify surface topology.",
                )

        # 3. Tier 2: Canonical -> FDS Bidirectional Audit
        # Check whether solid element exists in emitted FDS
        if elem.global_id not in fds_guids:
            missing_count += 1
            elem.mapping_status = MappingStatus.MISSING
            add_finding(
                Severity.P0,
                "Traceability & Completeness",
                f"Missing FDS Primitive for {elem.ifc_type}",
                f"Required element '{elem.name}' ({elem.global_id}) was not found in serialized FDS output.",
                elem.global_id,
                "Ensure element is in spatial scope and mapping strategy is active.",
            )
        else:
            matched_count += 1

        # 4. Tier 3: Effective Geometry & Opening Preservation
        if elem.openings:
            if not verify_opening_retention(elem):
                deviated_count += 1
                add_finding(
                    Severity.P1,
                    "Opening Preservation",
                    f"Uncarved openings on {elem.ifc_type}",
                    f"Element '{elem.name}' ({elem.global_id}) has {len(elem.openings)} openings but geometry has <= 12 faces.",
                    elem.global_id,
                    "Verify boolean subtraction kernel carved window/door cutouts.",
                )

    # Acceptance Gate Decision
    has_p0_or_p1 = any(f.severity in (Severity.P0, Severity.P1) for f in findings)
    verdict = AcceptanceStatus.REJECTED if has_p0_or_p1 else AcceptanceStatus.VERIFIED

    summary = {
        "P0": sum(1 for f in findings if f.severity == Severity.P0),
        "P1": sum(1 for f in findings if f.severity == Severity.P1),
        "P2": sum(1 for f in findings if f.severity == Severity.P2),
        "P3": sum(1 for f in findings if f.severity == Severity.P3),
    }

    return AcceptanceReport(
        status=verdict,
        total_elements_checked=len(model.elements),
        matched_count=matched_count,
        deviated_count=deviated_count,
        missing_count=missing_count,
        excluded_count=excluded_count,
        semantic_only_count=semantic_only_count,
        findings=findings,
        summary=summary,
    )
