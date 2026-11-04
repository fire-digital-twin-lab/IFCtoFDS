# R10-07 — Mode-specific Result Contracts / Hợp đồng đầu ra theo loại job

**Baseline:** R10-06 PR #28. **Source audit:** \`IFCtoFDS_Audit_2026-11-04.md\`, earlier review of conversion input/output and EV acceptance.

## Problem / Vấn đề

Previously \`JobService\` accepted any JSON object with a string \`status\`
as a completed non-inventory result and marked a job durable if the
\`status\` text was \`MAPPING_VERIFIED\`. The repository then assumed that
\`result["artifacts"]\` was a dictionary. A malformed or tampered result
could pass the completion boundary, produce an exception on GET /result,
or claim scientific acceptance without the necessary status fields.

## Changed / Đã thực hiện

- \`adapters/jobs/result_contract.py\`: explicit models for \`convert\`,
  \`scenario\`, \`preview\`, and \`inventory\`.
- \`JobService._loop()\`: validates the result against the job's **known mode**
  before \`COMPLETED\` or \`durable\`, retaining the original worker diagnostic
  on validation errors.
- \`JobRepository.read_result()\`: validates again after reading persisted JSON
  and before injecting whitelisted URLs, including preview geometry/MEP.
- \`tests/test_job_result_contract.py\`: valid modes, forged acceptance,
  contradictory verdicts, missing scientific fields, path-like artifact
  injection, invalid worker JSON, persisted-file mutation and preview links.
- \`tests/test_job_lifecycle.py\`: synthetic fixture for an inventory mode
  rather than claiming \`MAPPING_VERIFIED\` using status-only dummy JSON.

## Contract matrix / Ma trận hợp đồng

| Mode | Required result | Forbidden acceptance |
|---|---|---|
| convert | schema version, status, mapping_status, simulation_status, output_complete, gates, findings, coverage, artifacts | \`SIMULATION_VERIFIED\`; mismatched mapping/output_complete; bare status-only \`MAPPING_VERIFIED\` |
| scenario | \`status=COMPLETED\`, mesh, physics, \`simulation_status=NOT_RUN\`, verdict reason, evidence, scenario FDS | \`verdict=PASS\`, \`SIMULATION_VERIFIED\`, verdict inconsistent with failed gates |
| preview | \`status=PREVIEW_ONLY\`, \`verification=NOT_RUN\`, counts, bounds, source, display artifacts | Mapping or simulation verification |
| inventory | Element counts, storeys, sources, research metadata | Any overall scientific \`status\` |

Unknown modes are rejected. Result URLs are constructed by the server from
known artifact keys, not from worker-supplied URLs or relative paths.
Additive non-scientific fields remain accepted for backward compatibility.

## Trust and evidence boundary / Giới hạn

These schemas establish **structural and logical** validity only. They do
not independently prove that the physical model or the FDS output is correct.
Existing conversion auditing and the verified base-loader continue to
enforce source and geometry checks.

The SHA-256 of the conversion bundle covers mapping/FDS/source geometry
identity; it is not a full scientific audit-evidence manifest. A future
reviewed phase must independently bind persisted acceptance report, audit
checkpoint, geometry index, and result metadata in one evidence inventory
and prove crash/restart consistency. This should not be confused with the
R10-07 schema gate.

Do not promote \`NOT_RUN\` or \`INCONCLUSIVE\` to \`PASS\` to satisfy a schema.

## Exit criteria / Điều kiện nghiệm thu

- Python matrix, JS, browser and real FDS solver CI green on the latest commit.
- New negative tests prevent false \`MAPPING_VERIFIED\`, scenario PASS, bad
  artifact descriptors, and incorrect mode-specific results.
- API GET /result detects a mutated file and returns a controlled data error.
- Existing real IFC conversion and EV integration tests continue to pass.
- PR remains draft until review; no automatic merge.
