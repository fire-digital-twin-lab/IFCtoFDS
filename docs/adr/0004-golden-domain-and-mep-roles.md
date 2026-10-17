# ADR 0004 — Fixed domain and reference MEP (2026-10-16)

Status: accepted requirements from the current user instruction.

Supersedes the earlier remediation choice to expand MESH to contain whole
boundary-retained elements, and the earlier default of exporting all MEP solids.

Source geometry, retained canonical geometry, FDS representation and simulation
domain are independent. Scoped conversion requires an explicit domain. Unscoped
full-model conversion may freeze the full source domain. No padding/rounding of
MESH XB is allowed; IJK is chosen with ceil, actual cell dimensions are reported.

Cross-boundary elements retain full geometry, openings and the complete network.
No clipping, caps or logical connection removal is implemented. A boundary object
without effective-geometry evidence stays PENDING_VALIDATION, has no main FDS
primitive, and blocks mapping acceptance. The manifest/output are incomplete.

MEP defaults to REFERENCE_GEOMETRY outside FDS. Proxy/furniture/railing decisions
require explicit review. Promotion to PASSIVE_OBSTACLE needs a reviewed decision
covering IFC type, mesh scale, domain location, airflow clearance, system, future
operational use and golden policy. A decision is not proof of an operational model.

MAPPING_VERIFIED and simulation_status are separate. General mapping does not
require a fire scenario or operational equipment. Boundary treatment still needs
its specific solver evidence. SIMULATION_VERIFIED is reserved and never issued
by this stage. Missing research reference approval prevents research acceptance.

Golden candidates are drafts; counts and output from the converter are not their
own ground truth. The 124/120/4 historical numbers remain unvalidated context.
