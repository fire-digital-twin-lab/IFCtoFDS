# Artifact API 0.5 and structural OBST boundary evidence

This revision builds a new B1/B2 review baseline. It does not reconstruct an accepted historical FDS file, approve a reference, or establish simulation verification.

## API compatibility

`/api/convert` and `/api/jobs/{id}/result` return the same compact 0.5.0 summary: status, mapping/simulation status, profile, count coverage, timings, gate summaries, blocker count, at most 20 findings, research-source recognition and artifact links. Clients must download FDS, inventory, manifest and detailed reports separately. Code expecting `fds_text` or embedded geometry must migrate. Result size does not depend on triangle count when summary metadata is unchanged.

Geometry index JSON contains independent entity identities, common-world metre units, placement, mesh offsets/counts and SHA-256 payload references. Each payload stores contiguous Float64LE vertex triples then UInt32LE triangle triples. There is no audit quantization or simplification. Identical bytes can share a payload; identities cannot. `geometry_archive` contains `index.json` and its linked `index.payloads/*.bin`. The audit reader loads meshes individually. The viewer loads the reference layer on demand with at most two requests, cancels on job change/layer removal and disposes meshes. FDS is also downloaded as an artifact.

The 0.4 JSON reader remains available. Old bytes and approvals are checked in their original format. A new format/reference revision requires a new approval; an old VERIFIED label is not upgraded automatically.

The reference registry is operator configured with `IFCFDS_REFERENCE_CASES`, whose values may be paths or objects containing `path` and `name`. Public metadata contains only case ID/name, source hashes and approval status. Matching one source in a federation is PARTIAL recognition, not case acceptance. Generic `mapping` keeps research acceptance and unselected parity NOT_RUN; choosing research profile/reference is an explicit user action.

## Placement

Matrices are row-major arrays acting on column vectors in metres. Provenance records the IFC local-placement STEP chain, source unit scale, local-to-model matrix, federation matrix and effective world matrix. Mapped representation item transforms retain separate STEP identities and parent links. Mesh vertices already occupy common world metres: do not apply these matrices again. Audit rebuilds provenance from IFC; unsupported placement is explicitly unverified.

## Pinned solver setup

The project-local installer `python scripts/install-fds.py` downloads the Windows FDS 6.11.1 / Smokeview 6.11.2 package linked by [NIST](https://pages.nist.gov/fds/downloads.html), checks pinned package/binary SHA-256 and extracts the FDS binaries under `.deps`. It changes no system installation. See `installation.json` for origin and hashes.

Set `IFCFDS_SOLVER` to the extracted `firemodels/FDS6/bin/fds_openmp.exe`. Generate fixtures with `python scripts/certify-boundary-solver.py --help` and configure `IFCFDS_BOUNDARY_CERTIFICATE` for the server. CLI audit configuration uses `solver_executable`, `solver_evidence_directory` and `boundary_fixture_certificate`. Clients cannot select server executables or local evidence paths.

Runs retain exact FDS bytes, command, binary/input hashes, version output, stdout/stderr, exit/timeout status, .out/.smv and effective geometry. Output is not rewritten after solver evidence. A fixture certificate binds policy version, adapter code, solver binary and individual run files; the validator recomputes the fixture measurements rather than trusting saved PASS flags.

## Supported boundary policy

`VALIDATED_BOUNDARY_OBST_SINGLE_MESH` version 1.0.0 is opt-in. It accepts only proven closed axis-aligned structural column/wall/beam/slab boxes with no openings, MEP membership or unresolved role, in one explicit fixed domain. Canonical/package geometry remains the full source solid. FDS uses its positive-volume box intersection with the domain. Manifest stores both bounds and policy/evidence.

Before exact output audit the treatment stays PENDING_VALIDATION. VALIDATED requires independent source/package and FDS geometry gates, fixture certificate, pinned solver acceptance and effective geometry from SMV cell indices. Missing proof is INCONCLUSIVE; a confirmed deviation is REJECTED. A fixture PASS alone cannot validate a building.

GEOM, ramp/stair, rotated/non-box solids, MEP (including promoted MEP), HOLE/VENT and multiple MESH records remain unsupported for this policy. The effective adapter requires a uniform grid and unique nearest-grid rounding; half-cell ties remain INCONCLUSIVE. It checks obstruction occupancy, collapse/thickness and pairwise passage closure. It does not establish general ventilation connectivity or operational physics. SIMULATION_VERIFIED remains unavailable.

Pre-discretization tolerances remain 1 mm surface deviation, 0.1% relative volume and 0.999 solid IoU. Effective geometry uses grid-based checks, not the 1 mm threshold.

## Private baseline and reproducibility

`prepare-basement-review.py` verifies the external IFC hash, preserves all source geometry/connectivity, writes a DRAFT candidate, entity review CSV, source sections and domain-review record. Section planes are visual inspection aids, not approved air-domain limits. No private IFC or geometry is committed to public Git.

The first intake contains 5,641 products: 3,131 VALID meshes, 9 FAILED and 2,501 without representation. Candidate scope has 2,362 directly in-scope entities, 112 retained crossings, 2 unresolved and 3,165 out of scope. These are candidate counts, not approved expected results. Domain is deliberately unset pending review of spatial evidence. The nine geometry failures are retained.

Use `benchmark-revisions.py` with frozen revision directories, identical source/configuration and timeout 1800 seconds. It performs one warmup and three measured runs, recording elapsed time, peak process-tree RSS, stage timings where completed, artifact bytes and result bytes. Failures/timeouts remain in results. No speedup is claimed from incomplete runs. Defaults remain one active job, two waiting and 30 minutes.

## Evidence matrix

| Requirement | Regression/evidence |
|---|---|
| Compact result, binary integrity and rehashed geometry mutation | test_artifact_storage.py |
| Units, nested rotation, mapped origin and provenance mutation | test_placement_provenance.py |
| Source-preserving intersection and excluded boundary classes | test_boundary_policy.py |
| Real FDS acceptance, source mutation and 13 analytic fixtures | test_solver.py; boundary_fixtures.py |
| Scope, openings, federation, MEP, golden deltas, worker/upload/cancel | Existing Python/JavaScript suites |
| UI artifact links and no browser errors | qa-golden-browser.py (optional local Edge) |
| Windows/Linux environment regression | Conversion correctness CI |

Research acceptance still requires approved scope/domain, entity decisions, the whole reference bundle, independent source/golden checks and all applicable boundary evidence. Approval cannot override a technical gate.
