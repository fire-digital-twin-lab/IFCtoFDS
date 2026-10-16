# Mapping profiles and golden parity — schema 0.4.0

The current contract is defined here and in ADR 0004. Historical context documents
are preserved under `agent-context/`; the latest user decisions take precedence.

## Acceptance

`status` answers the requested profile. `mapping_status` and `simulation_status`
are always separate. Mapping returns MAPPING_VERIFIED only when its required gates
pass (or have a justified NOT_APPLICABLE). Known required failures take precedence
and return REJECTED. Missing decisions/evidence return INCONCLUSIVE.

Profiles:

- `mapping`: independent IFC inventory, source geometry, saved geometry package,
  FDS syntax/geometry, provenance, scope/domain, roles, openings and MEP.
- `research-basement`: the same plus an approved content-bound reference case.
- `simulation`: additionally requires solver/effective geometry, mesh, physics,
  operational and scenario evidence. This stage never emits SIMULATION_VERIFIED.

Solver/effective gates remain visible in a mapping report. Missing a solver does
not alone block interior source-to-FDS mapping. A boundary treatment still needs
its own solver/effective proof and blocks mapping until implemented/validated.
Legacy 0.3 manifests/reports can be read, but a legacy VERIFIED claim is never
promoted to MAPPING_VERIFIED. Independent re-audit and policy review are required.
CLI exit codes: 0 requested level achieved, 1 rejected, 2 inconclusive, 3 operational.

## Domain and geometry

Four distinct concepts are recorded: source geometry; retained canonical geometry;
FDS representation; simulation domain. A storey selector is source-qualified and
resolves through its building ancestry. Other buildings' elevations are not used
to infer the selected storey's upper interval. Repeated B1/B2 names must be selected
by identity; grouping across buildings is an explicit case decision.

Scoped conversions require an independent `simulation_domain`. The scope bbox is
not silently reused as the simulation domain. Full-model unscoped conversion may
freeze the full source bounds. MESH XB equals the domain; IJK uses ceil of extent
/ target cell size. The actual cell dimensions are reported. No padding or domain
expansion is performed to accommodate boundary-retained solids.

All source solids and network data are retained in the canonical/package artifacts.
A crossing element is PENDING_VALIDATION, is not serialized as a main FDS solid,
and makes the output incomplete/inconclusive. The manifest lists that element.
No clipping, caps or topology deletion occurs. VALIDATED_FDS_CLIPPING remains a
future policy; passing textual approval data cannot activate unsupported clipping.
An incomplete `.fds` is a diagnostic artifact and must be read with its manifest.
When no domain is configured, the diagnostic output lacks MESH and cannot run FDS.

## MEP and review decisions

Each record exposes source_presence, geometry_preservation, simulation_role,
operational_status, fds_representation, review_status, boundary_treatment and the
original source/IFC/type/system identities. REFERENCE_GEOMETRY has a real saved mesh;
it is different from a SEMANTIC_ONLY opening/port/spatial object.

MEP defaults to REFERENCE_GEOMETRY outside FDS, NOT_CONFIGURED operationally.
Proxy, furniture and railing objects require review. `include_review` remains a
compatibility input and grants no blanket exclusion/promotion approval.
Out-of-scope dispositions are EXCLUDED_SCOPE, separate from EXCLUDED_APPROVED.

Explicit decisions are keyed by source SHA256 + STEP ID:

```json
{
  "<source-sha>:123": {
    "action": "REFERENCE_GEOMETRY",
    "policy_version": "case-policy-1",
    "rationale": "Retain IFC equipment as reference only",
    "reviewer": "Named reviewer",
    "evidence": ["Review record and revision"]
  }
}
```

Actions are EXCLUDE, REFERENCE_GEOMETRY or PASSIVE_OBSTACLE. A passive promotion
also requires a `factors` object with nonempty descriptions for all seven keys:
ifc_type, mesh_scale, domain_position, airflow_clearance, system,
future_operational_role, golden_policy. These are review assertions and evidence
references, not automatic proof that an equipment interior or operating model
exists. Source/geometry/openings audits still run. No universal size threshold,
automatic duct bore, fan operation, sprinkler operation or inferred graph edge is
created. A declaration cannot waive a missing boundary/effective gate.

Classification uses instance and type class, predefined type, explicit system and
selected structured property evidence. Generic proxies remain reviewable. Local
system abbreviations such as SPR/PAD/CEAD are not universal classification rules.
Unresolved classification remains visible and can block acceptance.

## CLI and files

```powershell
python -m ifc_to_fds convert model.ifc --profile mapping --storey <qualified-storey> --domain 0 100 0 20 -9 0 -o run/model.fds
python -m ifc_to_fds convert model.ifc --config case-config.json --reference-case reference-cases/basement-b1-b2 --profile research-basement -o run/model.fds
python -m ifc_to_fds audit model.ifc --fds run/model.fds --manifest run/model_manifest.json --geometry-package run/model_geometry.json -o run/reaudit.json
python -m ifc_to_fds reference-candidate model.ifc --config reviewed-config.json -o .local-reference-cases/new-candidate
python -m ifc_to_fds reference-check .local-reference-cases/new-candidate
```

`reference-candidate` never approves and returns exit 2 for its DRAFT output.
It refuses to overwrite a nonempty reference directory. `reference-check` returns
2 for a draft; integrity errors return 3. There is deliberately no approve-all
command. The standalone audit defaults the geometry package path to
`<fds-stem>_geometry.json`; an absent package is INCONCLUSIVE, not inferred success.

Configuration extends the existing fields with `profile`, `simulation_domain`,
`reference_case`, `decisions`, `intentional_deltas`. The domain is an object with
xmin/xmax/ymin/ymax/zmin/zmax, all finite positive extents in common-world metres.
All source transforms remain explicit and independently re-read during audit.

Artifact set: FDS, manifest JSON/CSV, inventory, MEP graph, geometry package,
configuration, acceptance JSON/Markdown, parity JSON, timings and checksums.
The geometry package contains source-linked vertices/faces, openings, ports,
transforms, metres/frame and checksum. Audit compares it to fresh per-product IFC
geometry, bypassing converter cache; it uses the same underlying IfcOpenShell kernel.
The report stores independently measured preservation status. Merely recomputing
checksums after a mutation does not establish geometric equivalence.

## Reference bundles and intentional changes

The case directory contains sources, scope/domain, exact expected entity records,
structural/opening/HVAC/FP subsets, exclusions, boundary/alias decisions, golden
manifest/metrics, geometry package, graph, acceptance profile and review queue.
The bundle digest binds every evidence JSON in the declared inventory. Approval
is a separate record with status APPROVED, bundle_sha256, reviewer, rationale and
evidence. Editing an approved payload without updating the revision is rejected.
These are local review records, not cryptographic reviewer authentication.

The tracked basement case is DRAFT and contains no accepted entity list. Detailed
private intake lives under `.local-reference-cases/`, excluded from Git. External
source maps bind source SHA256 to local path; the resolver checks actual bytes.
A missing private fixture is RESEARCH_NOT_RUN, never a successful research run.

Golden parity compares source identities, exact entity sets, dispositions, roles,
ports/systems/edges, domain, tolerances, solid surfaces/volumes/IoU/components,
openings and actual FDS audit findings. IDs and serialized text order are not
geometric evidence. Equivalent vertex/triangle ordering and identical coplanar
surface partitions can pass; unsupported surface proofs remain INCONCLUSIVE.
Alias decisions preserve separate identities and require measured equivalent
solids under a rigid transform, plus review evidence.

Optional intentional_deltas JSON has status APPROVED, reference_digest and changes.
Each change supplies entity_key, field, before, after, rationale, reviewer, evidence.
The before value and baseline digest must match exactly. Supported fields are
explicit entity decision/identity fields and geometry. Deltas do not disable
source, fidelity, openings, boundary or topology gates. Adding/removing inventory
requires a new reviewed reference revision; it is not supported as a delta waiver.

Without the historical accepted FDS, a new candidate must be reviewed as a new
baseline. Matching it cannot be described as proven parity with the lost artifact.

## Web/API and validation limits

The web form separates selection volume from fixed domain, shows qualified
building/storey IDs, profiles, registered references, reviewed decision/delta JSON,
roles, blockers and download links. Reference meshes load in a separate viewer
group and are never inserted into generated FDS text by that viewer.

GET /api/reference-cases lists operator-registered IDs. Configure the server with
IFCFDS_REFERENCE_CASES as a JSON ID-to-directory mapping. Uploads may select an ID;
they cannot choose an arbitrary server file path. Jobs and cancellation retain the
existing bounded-process behavior. New artifact keys: geometry, parity, checksums.
Original upload filenames are retained as source metadata despite safe disk names.

Remaining research blockers: approved basement domain/scope/dispositions and
reference revision; real source geometry audit; validated boundary representation;
pinned real solver evidence. The existing solver adapter remains limited to the
single-mesh OBST subset. GEOM cut-cell, HOLE/VENT and multi-mesh effective geometry
are not made complete by this change. Operational physics is outside this stage.

Run Python tests, golden workflow JS, existing JS regressions and worker parity.
The optional external research runner exits nonzero when data/approval/evidence is
missing. Benchmark only a fixed commit/environment with one warmup and three
measurements; retain all failures/timeouts. Quick uses legacy representation rules,
so its timing must be accompanied by fidelity/coverage differences. Its audit now
runs in a separate bounded process rather than bypassing the deadline.
