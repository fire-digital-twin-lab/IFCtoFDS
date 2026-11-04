# R10-08 — Persistent Job Evidence Index / Chỉ mục bằng chứng lưu trữ

**Base:** R10-07 PR #29. R10-08 is stacked and must not merge before upstream.

## Problem / Vấn đề

A valid JSON schema is not proof that the FDS and independently audited
artifacts on disk are unchanged. Existing conversion manifest hashes bind
FDS, source mapping and geometry, but do not directly bind the delivered
`result.json` to the final acceptance report and checkpoint.

## Implemented / Đã thực hiện

For new `convert` and `scenario` jobs, the worker writes
`result_evidence.json` after writing `result.json` and before exiting
successfully. The index records SHA-256 of the **exact persisted bytes** of
result JSON and declared files. Files are hashed in streaming 1 MiB blocks.

- `JobService` requires this index before publishing `COMPLETED`, and
  before making a verified mapping result durable.
- `JobRepository.read_result` rechecks hashes on each API read and rejects
  modified/missing files with a controlled `ValueError` (HTTP 409 in API).
- Direct completed-job artifact URLs require an explicit declaration in
  that job's validated result; a globally registered filename alone is never
  download authorization. Geometry must also be declared by the job.
  Content-addressed geometry payloads are verified against their SHA-256
  filenames before download. Batch requests validate the complete result once,
  then check each individual payload.
- API evidence hashing runs outside the shared scheduler lock, preventing
  slow file reads from serializing every API job-status operation. The worker
  completion loop still has an existing locked verification section and
  requires separate profiling/refactoring before calling it optimized.
- Available report and manifest status fields are cross-checked even for
  overall INCONCLUSIVE/REJECTED conversions; only an overall
  MAPPING_VERIFIED result requires VERIFIED_SEALED.
- For missing indexes the API emits an explicit legacy/incomplete-job
  provenance-review error (HTTP 409), without modifying the old directory.
- For a conversion with **overall** `status=MAPPING_VERIFIED`, the index
  requires FDS, mapping manifest, independent acceptance report, geometry
  index and audit checkpoint. It checks status coherence across report,
  manifest and checkpoint; FDS SHA-256; geometry index checksum; and the
  reconstructed manifest bundle SHA-256.
- For a scenario, the index requires `scenario.fds` and checks its bytes
  against `evidence.fds_sha256`.
- Preview/inventory remain unaffected; they do not claim verified mapping
  and should not gain stronger verdicts by implication.
- A simulation profile whose mapping_status is MAPPING_VERIFIED but overall
  status is INCONCLUSIVE is **not** treated as VERIFIED_SEALED.

## Safety limits / Giới hạn quan trọng

This is **tamper evidence** for unintended modification, not an authentic
digital signature. An adversary with write access to all job files can
rewrite the artifact files **and** recompute the index. External trusted
storage, a signed digest and concurrency/locking are future concerns.

The index does not run CFD or evaluate scientific validity. A green
integrity check does not grant `SIMULATION_VERIFIED`, nor does it override
the independent IFC audit.

New convert/scenario results require the index. Historical jobs created
before this feature do not possess it, so their API reads will fail closed
rather than silently claiming integrity. A separate, explicitly reviewed
migration/verification procedure is required to restore access to legacy
completed results.

The index is written atomically as a single JSON file (temporary file then
rename). This does not imply atomic transactions across the entire job
directory. A crash before index creation prevents successful job publication.

## Tests / Kiểm thử

- Result, scenario FDS and index bytes modified or deleted after completion.
- Scenario evidence SHA mismatch before index creation.
- Repository read detects an altered persisted artifact.
- Real tiny-IFC conversion: acceptance report and manifest evidence checked,
  and report mutation detected.
- Overall INCONCLUSIVE simulation profile must not be falsely sealed.
- Existing complete Python/browser/JavaScript/FDS solver CI required.

## Remaining audit work

- Independent signature or externally anchored digest for adversarial tamper resistance.
- Crash/restart recovery and verified historical-job migration.
- Large-IFC benchmark of evidence hashing cost; measure both API paths and
  worker completion, including lock hold times, with reproducible fixtures.
- Potential file replacement between verification and FileResponse streaming
  (time-of-check/time-of-use) requires immutable sealed storage or filesystem
  snapshot semantics; no claim of adversarial tamper protection is made.
- Full solver log and scientific evidence record linking.
