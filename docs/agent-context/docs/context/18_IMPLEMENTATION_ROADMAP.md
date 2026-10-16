# 18 — Kế hoạch phát triển end-to-end theo phụ thuộc

## Ưu tiên kỹ thuật

**P0 trước:** baseline/inventory → geometry openings/transforms/units → canonical model → mapping → MEP graph → audit → Web integration. Một số module có thể phát triển song song sau khi schema ổn định, nhưng không release Verified trước các gate.

| Giai đoạn / PR | Phạm vi | DoD / dữ liệu chứng minh |
|---|---|---|
| Phase 0 / PR-00 | Audit fork HEAD, checksum, tests, risk register, docs as-is | baseline test logs + architecture ADRs |
| Phase 1 / PR-01 | Python IfcOpenShell CLI + complete inventory + source/file metadata | FZK/Duplex inventory kiểm tra được, schema validated |
| Phase 2 / PR-02 | Canonical geometry: units/placements/voids/mapped item/shape validity | golden geometry fixtures pass |
| Phase 3 / PR-03 | Semantic system/MEP graph HVAC/PCCC + source completeness | graph test + system-level report |
| Phase 4 / PR-04 | Scope policy + geometry mapping policies + FDS exporter canonical integration | OBST/HOLE/GEOM round-trip, mapping manifest |
| Phase 5 / PR-05 | Independent validation + mutation/acceptance gates | detects seeded bugs, report accepts/rejects correctly |
| Phase 6 / PR-06 | Web FastAPI bridge + source/system tree + audit 3D overlay | complete Verified E2E, legacy preserved |
| Phase 7 / PR-07 | Large IFC profiling/caching, technical security/CI, official FDS checks | raw benchmark + regressions + limits |
| Phase 8 / PR-08 | Research docs, comparison upstream/BFDS, reproducible release | paper-ready tables (không bịa số), release notes |

## Vertical slices phải có

- **VS-1:** IFC một tường + opening → inventory → canonical → FDS → reparse → finding; hoàn thành trước thêm hàng chục loại IFC.
- **VS-2:** Multi-IFC + consistent transforms → subset theo scope → manifest.
- **VS-3:** One HVAC duct/fitting/fan network + one FP pipe/sprinkler fixture → graph + semantic/geometry policy + audit.
- **VS-4:** Web tải IFC → backend conversion → status → output + audit overlay.

## Vì sao không triển khai toàn bộ một lần

- Interface JSON/binary chưa chốt có thể gây refactor hàng loạt.
- Cùng lúc rewrite JS exporter và Python core gây khó biết lỗi thuộc module nào.
- Khi worker inline không rebuild, Web chạy logic stale khiến test/preview sai.
- MEP graph/physical simulation dễ bị trộn, làm sai mục tiêu nghiên cứu.

## Lời hứa không được đưa ra khi chưa có bằng chứng

- “100% accuracy trên mọi IFC”, “FDS ready-for-fire-simulation”, “quạt đang hoạt động”, “sprinkler đã sẵn sàng”, “Hiệu năng hơn upstream X%”.

## Nhiệm vụ ngay cho coding agent

1. Xác minh repo HEAD/branch/worktree/tags và chạy baseline; báo file list.
2. Tạo `docs/audit/00-baseline.md`, `docs/architecture/as-is.md`, ADR 001–003, PR plan.
3. Dựng Python package minimal với `inspect` CLI và schema source inventory, có fixture test.
4. Không commit trực tiếp main; tạo PR có evidence, chờ kiểm toán sau đó tiếp tục.
