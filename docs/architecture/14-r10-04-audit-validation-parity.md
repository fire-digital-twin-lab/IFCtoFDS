# R10-04 — Independent audit decomposition and validator parity / Phân rã hậu kiểm

**Baseline:** R10-03, PR #24, SHA `83ab0726c4776ac64c428c4db1001d08c4df5b75`
**Policy:** never replace a safety-critical evaluator based only on an architectural resemblance.

## 1. Source-level analysis / Phân tích mã nguồn

There are two related but distinct validation workflows:

1. `validation.engine.run_independent_validation` is the current
   authoritative mapper audit: it parses FDS, traces individual primitives,
   compares source solids, opening passages and mesh-domain consistency,
   checks source defects, and runs/blocks solver evidence as configured.
2. `validation.runner.ValidationRunner` orchestrates modular checkers and
   creates an `AcceptanceReport` using `AcceptanceEvaluator`. It has
   comparable gates but has **not** proven full parity across every source,
   evidence field, error path and solver mode.
3. `AuditConversionUseCase` is an enclosing independent-source workflow.
   It **re-reads IFC** rather than accepting the converter's in-memory model,
   checks source geometry package and placement, verifies manifest source
   hashes, domain, boundary decisions, MEP graph, golden reference, coverage
   and report sealing. Replacing only the validation engine would not
   reproduce those enclosing checks.

The existing `tests/test_validation_engine_parity.py` cover eight representative
patterns (clean source, shifted solid, omitted solid, unexpected primitive,
invalid namelist, air leak, legacy comments, unauthorized representation),
but do not prove complete report parity or the outer audit lifecycle.

**Kết luận:** không thay `engine.py` bằng `ValidationRunner` trong PR này.

## 2. Separation and ownership / Ranh giới

| Responsibility | R10-04 owner | Guardrail |
|---|---|---|
| Source re-read and engine invocation | `AuditConversionUseCase` | Preserve original ordering |
| Source/package/placement/manifest integrity | `application/services/audit_integrity.py` | Compare independently reconstructed evidence |
| MEP saved graph and coverage aggregation | `application/services/audit_mep_coverage.py` | No converter-side in-memory trust |
| Reference/parity gate and report sealing | `AuditConversionUseCase` | Finalize after golden reference |
| Engine vs runner diagnostics | `validation/parity_contract.py` | **No promotion of a candidate to authority** |

The extracted post-engine blocks retain the original order, mutation semantics,
reason strings and gate names. No numerical tolerances, IFC geometry algorithm,
FDS output generation, independent auditor or solver configuration change.

## 3. Full parity acceptance matrix / Ma trận tương đương bắt buộc

| Dimension | Must compare before replacement |
|---|---|
| Final verdict | `status`, `mapping_status`, `simulation_status` |
| Gates | same gate set, `status`, `required`, reasons, codes and evidence |
| Elements | full source keys, status, counts and missing/unsupported/deviated cases |
| Identity/provenance | IFC SHA, GlobalId, STEP, source_id, placement, world transform |
| Geometry | surfaces, volume, solid IoU, mesh bounds, opening passage |
| MEP | graph edges, ports, systems, orphan classification and findings |
| Partial/failure | source preflight, `NOT_RUN`, `INCONCLUSIVE`, thrown exceptions |
| Execution | solver and effective-geometry evidence, timeout, disabled solver |
| Reference | golden parity, reference approvals, source geometry package integrity |
| Output | manifest, mapping status, coverage, findings and serialized report |

Hard blocker: a missing gate, a changed `required` flag, positive verification
without source proof or missing evidence must not be silently accepted.
The comparison helper `compare_validation_reports()` is fail-closed:
it reports both missing and additional gates, verdict and entity/count
divergence, and in detailed mode compares reasons, findings, coverage,
evidence and deterministic metrics. It **does not run** a second solver
or modify production acceptance status.

The comparator deliberately has a baseline reporting mode because the
existing implementations may disagree on descriptive coverage and evidence.
A mode showing no status mismatches is **not** a waiver for unproven evidence.

## 4. Verification strategy / Chiến lược kiểm thử

- Freeze CI baseline from R10-03; Python, browser, JS, real FDS.
- Keep the existing eight engine/runner parity tests.
- Test parity comparator with injected verdict, gate, evidence, metric and
  entity mutations. Ensure absent/extra gates are reported.
- Test extracted steps with source topology preflight and saved-MEP
  mismatch/no-graph cases; preserve audit ordering.
- Maintain frozen IFC behavioral cases A–F and scientific artifacts.
- Later, add independently sourced IFC corpora including opening-rich,
  federated, HVAC, malformed and negative-geometry cases; compare strict
  reports and evidence before any validator switchover.

## 5. Definition of done / Điều kiện hoàn thành

This PR may be merged when all existing CI jobs and new tests pass,
without changed verdicts, source geometry, FDS artifact bytes or gate
semantics. This **does not** authorize switching to `ValidationRunner`;
that requires separately verified strict parity on real and mutated corpora.

[VI — Các nguyên tắc cốt lõi] Không biến `NOT_RUN` thành `PASS`, không
đánh đồng chứng cứ đầu ra của converter với kiểm định nguồn IFC độc lập,
không thay thuật toán hình học đồng thời với việc di chuyển mã.

[Prior stage](13-r10-03-conversion-checkpoints.md)
