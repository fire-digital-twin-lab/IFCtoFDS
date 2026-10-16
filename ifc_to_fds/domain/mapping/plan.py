"""MappingPlan builder and inspection utilities."""

from .model import MappingDecision, MappingPlan
from ..bim.model import CanonicalModel


def build_mapping_plan(
    model: CanonicalModel, cell_size: float = 0.2
) -> MappingPlan:
    """Constructs an immutable MappingPlan from canonical elements after mapping policy execution."""
    decisions = []
    for e in model.elements:
        decisions.append(
            MappingDecision(
                entity_key=e.entity_key,
                strategy=e.mapping_strategy,
                simulation_role=e.simulation_role,
                fds_representation=e.fds_representation,
                fds_primitive_ids=list(e.fds_primitive_ids),
                representation_bounds=e.representation_bounds,
                rationale=e.mapping_rationale,
                boundary_treatment=e.boundary_treatment,
            )
        )
    return MappingPlan(
        decisions=decisions,
        simulation_domain=model.simulation_domain,
        cell_size=cell_size,
        metadata={
            "source_id": model.source.source_id,
            "filename": model.source.filename,
            "total_elements": len(model.elements),
        },
    )
