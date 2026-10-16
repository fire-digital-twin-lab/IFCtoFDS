# 24 — Requirement → module → test → artifact (traceability matrix)

| Requirement | Module chính | Test/Gate đề xuất | Evidence artifact |
|---|---|---|---|
| REQ-001 | Source ingestion/run store | source hash and immutability, G0 | source-files.json, run-metadata.json |
| REQ-002 | Federation | T-04,T-13,G1 | transforms.json + geometry comparisons |
| REQ-003 | Inventory | T-01,G2 | source-inventory.json, coverage.csv |
| REQ-004 | Semantic classifier | T-15,G2 | element-classification.csv |
| REQ-005 | Geometry kernel | T-02,T-03,T-04,T-14,G1 | geometry-comparison.csv |
| REQ-006 | Opening/connectivity QA | T-02,T-11,T-16,G1/G4 | openings.json, findings.csv |
| REQ-007 | HVAC system mapper | T-05,T-06,G2 | mep-systems.json |
| REQ-008 | PCCC system mapper | T-15,G2 | fp-inventory.json |
| REQ-009 | MEP graph | T-05,T-06,G2 | mep-connectivity.json |
| REQ-010 | Mapping policy | T-15/T-16,G3 | mapping-manifest.json |
| REQ-011 | Scope resolver | T-07,T-13,G3 | scope.json + scope-diff.csv |
| REQ-012 | Provenance | T-10,T-18,G3 | mapping-manifest.json |
| REQ-013 | Alias verifier | T-18,G3 | alias-evidence.json |
| REQ-014 | Geometry auditor | T-02,T-10,T-11,G4 | geometry-comparison.csv |
| REQ-015 | Acceptance engine | T-10,T-11,G4 | findings.csv, acceptance.json |
| REQ-016 | Export/artifact service | export round-trip,G3/G6 | converted.fds and artifact hashes |
| REQ-017 | Legacy frontend/worker | T-09,G0/G5 | compatibility test logs |
| REQ-018 | CLI/FastAPI | CLI E2E + API E2E,G5 | command logs/api artifacts |
| REQ-019 | Test/CI | T-01 through T-18 | machine-readable junit/CI logs |
| REQ-020 | License/Git governance | G0+review | license inventory and PR reports |
| REQ-021 | Generic scope | T-07,T-13,G3 | cross-building fixtures |
| REQ-022 | Tolerance profiles | geometry metric threshold tests | conversion-config.json |
| REQ-023 | Human review | review override tests,G4/G5 | decisions.json |
| REQ-024 | Web visualization | Viewer E2E,G5 | screenshot/test log |
| REQ-025 | Performance | benchmark suite,G6/G7 | benchmark raw files |
| REQ-026 | Quick vs Verified | route test,G5 | UI/E2E logs |
| REQ-027 | Optional tooling | tool-specific fixtures/review | optional compare reports |

## Giải thích

IDs test chi tiết trong `16_TEST_AND_BENCHMARK.md`, acceptance gates trong `17_ACCEPTANCE_GATES.md`, business definitions trong `01_REQUIREMENTS.md`. Khi thêm/sửa requirement phải cập nhật bảng, thêm test hoặc nêu lý do explicit `NOT_TESTABLE_YET`. Bảng này là **kế hoạch traceability**, không phải kết quả test đã đạt.
