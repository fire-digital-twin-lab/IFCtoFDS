# R10-05b — Verified checkpoint consistency and atomic sealing

**Base:** stacked on R10-05 PR #26; no changes to scientific mapping
or validation algorithms. Review and merge R10-05 first.

## Problem / Vấn đề

The former workspace implementation set `VERIFIED_SEALED` whenever
`status == MAPPING_VERIFIED`, even if `manifest.output_complete=False`.
That produced a self-contradictory checkpoint. Further, directly overwriting
the JSON manifest and checkpoint could leave a truncated file after a crash.

## New sealing invariants / Điều kiện niêm phong

Before accepting a positive `MAPPING_VERIFIED` checkpoint, require:

1. `manifest.output_complete is True`.
2. `manifest.mapping_acceptance == MAPPING_VERIFIED`.
3. `manifest.acceptance_status == MAPPING_VERIFIED`.
4. Canonical 64-digit lowercase SHA-256 `bundle_sha256`, equal to
   `manifest.compute_bundle_sha256()`.
5. A persisted `model.fds` whose SHA-256 matches `manifest.fds_sha256`.

A mismatch raises `ValueError` **before writing any final artifact**, retaining
the prior `NOT_RUN` or `DRAFT_NOT_SEALED` state. This does not invent a new
acceptance proof; it checks consistency of evidence already produced.

Checkpoints for non-verified reports remain unsealed as before.
The mapping and simulation acceptance gates remain independent.

## Atomic files / Ghi nguyên tử

Final manifest and checkpoint JSON are written via unique same-directory
temporary files followed by atomic rename. `model_manifest.json` is
committed first; `audit-state.json` is committed **last** so an interrupted
write cannot falsely publish a completed checkpoint.

This protects individual file replacement but **is not a cross-file
transaction**. Full crash recovery, atomic creation of draft artifacts,
and process concurrency locking are future tasks.

## Tests / Kiểm thử

`tests/test_conversion_workspace.py` includes:
- Valid consistent sealing and unchanged unverified statuses.
- Missing FDS and mismatched stored FDS SHA-256.
- Missing/contradictory mapping acceptance or output completeness.
- Corrupt bundle hash, unchanged unsealed checkpoint and no partial files.

Scientific source re-read, FDS serializer, tolerances, mapping algorithm,
and independent audit policies have not changed.
