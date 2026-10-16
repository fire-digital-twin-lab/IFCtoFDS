# Historical schema 0.3 conversion guide

**Superseded by [schema 0.4 mapping profiles and golden parity](golden-mapping-parity.md).**
The text below records previous behavior; its expanding-domain, MEP-export and
VERIFIED rules do not describe current conversion. Use the linked guide for CLI,
configuration, acceptance and artifact contracts.

# Verified conversion: usage and evidence limits

This development branch separates conversion from acceptance. Creating an FDS file,
matching source IDs, or successfully starting FDS does not by itself verify a model.
Schema version is `0.3.0`; canonical/manifest formats from `0.2.0` must be regenerated.

## Install and run

Use Python 3.11 or 3.12 and Node 22 or newer for the JavaScript checks.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
.venv\Scripts\python -m pip check
.venv\Scripts\python -m ifc_to_fds serve
```

Open `http://127.0.0.1:8000`. Quick mode is browser-only. Verified mode uses the
same-origin page served by this backend. Select sources, read their inventory,
select storeys and/or a bounding box, and start conversion. Cancellation stops the
worker and its children. Viewer clipping changes visibility, not export scope.

For multiple sources, confirm a shared coordinate system or enter per-source
translations and rotation about Z in the web form. CLI configuration supports full
rigid 4x4 transforms. No alignment by bounding boxes or merging by GlobalId occurs.

```powershell
python -m ifc_to_fds inventory examples/AC20-FZK-Haus.ifc --json
python -m ifc_to_fds convert examples/AC20-FZK-Haus.ifc --storey Erdgeschoss --all-geom -o output/model.fds
python -m ifc_to_fds audit examples/AC20-FZK-Haus.ifc --fds output/model.fds --manifest output/model_manifest.json -o output/reaudit.json
python -m ifc_to_fds convert architecture.ifc mep.ifc --common-coordinates --config configuration.json -o output/federated.fds
```

Exit codes: `0 VERIFIED`, `1 REJECTED`, `2 INCONCLUSIVE`, `3 operational/configuration
error`. Reports and converted FDS are saved for rejected/inconclusive conversions.
The default filename ends in `_converted.fds`; only the web download of a verified
result receives `_verified.fds`.

Example configuration (transform translations and scope coordinates are in metres):

```json
{
  "cell_size": 0.2,
  "all_geom": true,
  "include_review": false,
  "sources": {"common_coordinates": true},
  "scope": {
    "storeys": [],
    "bounding_box": {"xmin": 0, "xmax": 20, "ymin": 0, "ymax": 30, "zmin": -4, "zmax": 0}
  },
  "audit": {
    "surface_tolerance_m": 0.001,
    "relative_volume_tolerance": 0.001,
    "min_solid_iou": 0.999,
    "solver_version": "6.11.1",
    "solver_timeout_s": 120
  }
}
```

Alternatively `sources.transforms` maps source SHA-256 or zero-based input index to
a row-major 4x4 matrix. Every source needs a transform unless common coordinates
are confirmed. Reflections/scales are rejected; units are normalized separately.
Storey names must identify exactly one source-qualified storey. Unknown/ambiguous
storeys and empty scope are errors. Whole intersecting solids are retained with
`BOUNDARY_RETAINED`, including source and rationale. They may extend the final MESH.

## Acceptance and independence

Required gates are syntax, source inventory, traceability, scope, geometry, openings,
MEP, solver initialization, and effective geometry. A failed required gate gives
`REJECTED`; otherwise missing/unsupported evidence gives `INCONCLUSIVE`. Only complete
required evidence can produce `VERIFIED`.

The standalone audit reopens the original IFC files, verifies hashes, rebuilds
reference geometry per product without converter cache/iterator, reconstructs the
MEP graph and reparses the serialized FDS. The audit shares IfcOpenShell with the
converter; this is independence of data flow, not an independent IFC geometry kernel.
Manifest decisions are compared with independently reconstructed scope/mapping.
Supply a trusted configuration when auditing an untrusted manifest policy.

All IfcProduct entities, including openings and ports, remain in the inventory.
Openings/ports/spatial entities have explicit semantic dispositions, not solids.
Physical entities with failed/missing geometry remain required and cause a failure.
MEP solids are preserved by default. Review-solid exclusions apply to furnishing,
building proxies and railings, with explicit rationale. Flow classification uses
IFC classes, predefined types, systems and fallback names; ambiguity is reported.

The converter chooses OBST only for a closed positive-volume solid proven to be an
axis-aligned box. Other valid solids use GEOM. Invalid meshes are never replaced
by their bounding box. VOXEL/OBST_HOLE are not implemented in the Python serializer.

Solid comparisons use volume, area, Boolean IoU, connected components and surface
distance. Corresponding triangles or proven boxes provide a whole-surface distance
bound. With different triangulations, sampled distances can reject deviations but
cannot establish a complete pass; the gate remains inconclusive. Nonadjacent triangle
crossings and overlapping closed components are checked; this is not a general proof
against all numerical/pathological triangle degeneracies.

Opening checks intersect actual source opening solids with source/output hosts and
compare aggregate free volumes and their connected components, including source
door/window fills and other obstructions. No triangle-count heuristic is used.
This tests geometric preservation; transient door operation and HVAC flow are outside
the implemented scope.

## FDS evidence and remaining release blockers

The solver adapter requires FDS **6.11.1**, records executable SHA-256, reported
version, command outcome and logs, and uses an isolated directory. Configure the
local operator's executable with `IFCFDS_SOLVER` or CLI `--solver`. Uploaded HTTP
configuration cannot select an executable.

The effective geometry adapter reads actual single-mesh OBST grid indices from the
solver's SMV output and TRNX/TRNY/TRNZ coordinates. It checks source identities,
displacement against half-cell widths, collapsed solids and closed pairwise gaps.
This subset does not cover dynamic obstructions or arbitrary multiphysics inputs.

**GEOM cut-cell output, HOLE/VENT effective geometry, and multiple FDS meshes still
return INCONCLUSIVE.** The FDS binary is not bundled. The real solver suite must run
on a configured FDS 6.11.1 runner before release; parser fixtures are not solver-run
evidence. Most building conversions include GEOM and therefore cannot currently
receive complete acceptance. Do not merge this development work as research-ready
until those output adapters and solver evidence are completed.

Format references: [NIST manuals](https://pages.nist.gov/fds/manuals.html),
[FDS 6.11.1 SMV writer](https://github.com/firemodels/fds/blob/FDS-6.11.1/Source/dump.f90),
[IfcOpenShell iterator](https://docs.ifcopenshell.org/ifcopenshell/geometry_iterator.html),
[Trimesh Boolean backend](https://trimesh.org/trimesh.boolean.html).

## HTTP interfaces and operational limits

- `POST /api/inventory`: legacy `file` or repeated `files`; returns source hashes and qualified storeys.
- `POST /api/jobs`: repeated multipart `files` and JSON `configuration`; returns `202` and job ID.
- `GET /api/jobs/{id}`: `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`, `TIMED_OUT`.
- `DELETE /api/jobs/{id}`: stop a pending/running job and remove source temporaries.
- `GET /api/jobs/{id}/result`: result, report, manifest, inventory, MEP and configuration.
- `GET /api/jobs/{id}/artifacts/{kind}`: `fds`, `manifest`, `manifest_csv`, `report`, `markdown`, `inventory`, `mep`, `configuration`.
- `POST /api/convert`: legacy single-file compatibility, using the same isolated job pipeline.

Defaults: loopback binding, same-origin mutation requests, one running job, two
waiting jobs, maximum 16 sources, 200 MiB/source, 500 MiB/job plus 1 MiB multipart
overhead, deadline 1,800 seconds. Artifacts expire after one hour. Only public web
assets are served; repository internals and job directories are not static assets.

Operator environment variables: `IFCFDS_MAX_WAITING`, `IFCFDS_TIMEOUT_S`,
`IFCFDS_MAX_FILE_BYTES`, `IFCFDS_MAX_JOB_BYTES`, `IFCFDS_JOB_ROOT`, `IFCFDS_SOLVER`,
`IFCFDS_GEOMETRY_CACHE`. Converter geometry cache defaults to `.cache/geometry` and
is keyed by source hash, engine/schema/settings. Independent audits bypass it.
The service is designed for a single local process, not multiple web server workers.

## Tests and benchmarks

```powershell
python -m pytest -q
node scripts/test-verified-regressions.js
node scripts/test-geom-opening-regression.js
node scripts/test-background-export-worker.js
node scripts/generate-inline-parse-worker.js
node scripts/generate-inline-export-worker.js
git diff --exit-code -- js/workers/*-inline.js
python -m pytest -q -m solver
python scripts/benchmark.py --repeat 3 --warmup 1 --timeout 120
```

Normal tests deselect the solver marker; explicitly requesting `-m solver` fails
when no solver is configured. CI defines a manual job for a self-hosted
`fds-6.11.1` runner and stores its evidence. Windows/Linux Python CI and JavaScript
CI are ordinary push/PR checks.

The benchmark runs Quick, Python all-GEOM and mixed conversion on the three bundled
IFCs, retains failed/timed-out runs, records source hashes, timing, peak process-tree
RSS and reports. Warmups are marked and must be excluded from summary statistics.
Quick subprocess timing includes parse/export; its subsequent audit is separate.
Python subprocess timing includes conversion and audit; compare the recorded stage
timings when comparing parse/export performance. Results are local under
`benchmark-results/` and should accompany a fixed revision and environment before
being used as scientific evidence.
