# Review remediation status — 2026-10-16

Base: `feature/verified-ifc-fds-framework`, `bcd23aefc1810f90a58bed4fc79f25481844fe25`.
Work branch: `codex/verified-correctness`, created after fetching origin.
The context SHA-256 index supplied at root is preserved; its missing 32 documents
were not treated as content that had been read.

## Implemented behavior and evidence

| Review issue | Implementation | Evidence |
|---|---|---|
| P0-01 false VERIFIED | Explicit required gates, parsed coordinates/faces, source re-read, rejection/inconclusive precedence | Shifted OBST/GEOM, removed/extra primitive, manifest/hash/source mutations, gate truth table |
| P0-02 unsafe OBST | Prove closed axis-aligned box; otherwise GEOM; invalid solids remain failures | Rotated box, missing mesh and positive box fixture |
| P0-03 overwritten scope | Geometry precedes selection; separate decisions; serializer consumes a mapping plan | Scope-to-FDS test checks actual serialized source set; ambiguous storeys rejected |
| P0-04 opening heuristics | Boolean host/void intersections and aggregate free-volume/component comparison | Source wall test and deliberately resealed host/blocked passage fixtures |
| P0-05 preview/export shortcut | Dedicated GEOM mesh/completeness; export reparses without skip; BSP solid subtraction | Preview shortcut must refuse GEOM export; rays through every FZK exterior-wall opening |
| P0-06 MEP accounting | Source-qualified systems/ports/edges, placement, classification evidence and system coverage | Exact IFC2X3/IFC4 graph fixtures, deduplicated systems, source graph mutation |
| P1 iterator/cache | Multicore iterator with diagnosed per-product fallback; source/settings cache | Bundled IFC geometry test; independent audit bypasses converter cache |
| P1 mesh validity | Index/finite/degenerate/manifold/orientation/volume and crossing/component checks | Invalid index, resealed geometry and overlapping components |
| P1 federation/units | Multiple sources, explicit rigid transforms, qualified entity/storey keys, recursive units | Duplicate GlobalId, duplicate file, coordinate confirmation, rigid transform, inch and mm fixtures |
| P1 CI/install | Python Windows/Linux matrix, JS tests, generated bundle parity, separate solver suite | Clean local venv install and dependency check; CI workflow added, remote runs not claimed |
| P1 API/UI | Bounded uploads, queue, isolated inventory/conversion worker, timeout/cancel, public static whitelist, text rendering | API limit/origin/private-file tests; live browser conversion with zero page errors |

Local verification at the implementation checkpoint: **51 Python tests passed, one
real-solver test deselected**; Ruff passed. The clean environment installed only
declared project/test dependencies and `pip check` passed. Upstream library warnings
about zero-volume mass properties and the Starlette TestClient deprecation were
observed. They were not hidden or interpreted as successful solver evidence.

JavaScript tests passed for canonical export completeness, opening rays, provenance,
the existing GEOM regression and background/direct-file workers. Inline worker
bundles were regenerated from source.

The browser check selected a generated IFC fixture, fetched storeys, selected a
qualified storey, submitted a job, and displayed INCONCLUSIVE with implemented gates
passing and solver/effective evidence unavailable. Local screenshot:
`scripts/out/verified-ui-final.png` (ignored artifact).

## Remaining work before the full four-stage plan is complete

- Implement and validate GEOM cut-cell output reconstruction against FDS 6.11.1.
- Extend effective geometry beyond the current single-mesh OBST subset to HOLE/VENT
  and multiple FDS meshes.
- Run the real solver suite on an installed pinned binary; there is no local FDS
  installation and no claimed solver PASS evidence.
- Review numerical/pathological self-intersection and differing-triangulation
  surface proofs; unsupported cases deliberately remain inconclusive.
- Expand MEP ground truth to richer fittings/devices and cross-scope networks;
  explicit port ownership/connectivity fixtures cover IFC2X3 and IFC4.
- Create and review stage PRs and run the new remote CI. No merge to dev/main
  is justified by the local checks alone.

The local three-model benchmark is an exploratory implementation run with a
30-second configured per-conversion deadline, one warmup and three measured runs.
It includes timeouts and findings, and ran while implementation was changing.
It must not be used as a fixed-revision scientific benchmark or a speedup claim.
Rerun the documented harness on a frozen revision/environment for research evidence.

Full usage, schema changes and limitations: [Verified conversion guide](verified-conversion.md).

## Exploratory benchmark outcome

All 36 runs (including warmups) were retained. The table uses measured runs only.
Times include the configured deadline for timed-out runs and are not completion
latencies. The run was not fixed-revision evidence.

| Model | Method | Measured runs | Timeouts | Median observed seconds |
|---|---|---:|---:|---:|
| AC20-FZK-Haus.ifc | quick | 3 | 0 | 0.56 |
| AC20-FZK-Haus.ifc | all_geom | 3 | 1 | 19.86 |
| AC20-FZK-Haus.ifc | mixed | 3 | 3 | 30.07 |
| AC20-Institute-Var-2.ifc | quick | 3 | 0 | 8.98 |
| AC20-Institute-Var-2.ifc | all_geom | 3 | 3 | 30.11 |
| AC20-Institute-Var-2.ifc | mixed | 3 | 3 | 30.09 |
| IfcOpenShell-Duplex.ifc | quick | 3 | 0 | 0.96 |
| IfcOpenShell-Duplex.ifc | all_geom | 3 | 3 | 30.07 |
| IfcOpenShell-Duplex.ifc | mixed | 3 | 3 | 30.07 |
