# 06 — Findings từ audit ZIP v0.1.0: chặn nghiệm thu

**Nguồn:** bản snapshot `IFCtoFDS_v0.1.0_Code_Audit.md`, review 2026-10-15. Đây là findings cho bản ZIP, không tự coi còn tồn tại trên commit mới. Mỗi lỗi phải được agent tái hiện/test rồi đóng bằng chứng.

**Định nghĩa severity:** P0/P1 ở đây = **chặn nghiệm thu theo scope nghiên cứu**; có thể công cụ demo gốc vẫn chạy trong phạm vi thiết kế ban đầu.

| Finding | Severity | Bằng chứng nguồn (mốc tệp snapshot) | Hành động + regression cần có |
|---|---|---|---|
| IFC-001 | P0 | `ifc-adapter.js` PRODUCT_TYPES allowlist | Inventory hết `IfcProduct` theo schema; fixtures covering/footing/ramp/MEP |
| IFC-002 | P0 | MEP xếp `review`, bỏ mặc định | Source inventory và chính sách MEP riêng; không mặc định loại mà không lý do |
| IFC-003 | P0 | Không có system/port/connectivity graph | Trích nguồn IFC relationships, graph coverage tests |
| IFC-004 | P0 | `compare/checks.js` sanity-only | Independent IFC+serialized FDS audit, mutation tests và gate |
| IFC-005 | P1 | displayMesh có openings, exportMesh không carve | Golden wall FZK 3 openings, cả GEOM/OBST-HOLE paths kiểm tra geometry |
| IFC-006 | P1 | `MappingOrigin` thiếu inverse transform | Fixture rotated/mirror/offset mapping origins |
| IFC-007 | P1 | PolygonalBoundedHalfSpace xấp xỉ plane infinite | Polygon-limited clipping fixture hoặc `UNSUPPORTED` có evidence |
| IFC-008 | P1 | SI-only length unit detection | mm + conversion-based feet, explicit transforms |
| IFC-009 | P1 | Viewer clip không phải export scope | Tests so sánh viewerClip/exportScope; boundary intersections |
| IFC-010 | P1 | GEOM invalid chưa block; không có solver check | Static geometric validity gate; solver evidence khi có executable |
| IFC-011 | P2 | Summary trước fallback không khớp primitives | Reparse FDS và đối chiếu emitted primitive stats |
| IFC-012 | P2 | Provenance thiếu Storey/System/Tag | Sidecar manifest và trace per primitive |
| IFC-013 | P2 | Docs count khác thực tế | Generate metrics từ tests, snapshot metadata, không hardcode counts |
| IFC-014 | P2 | CDN/WebIFC phụ thuộc network | Dependency pin, offline install strategy, reproducibility |
| IFC-015 | P2 | FDS filename sinh từ IFC không có lineage đầy đủ | Run ID, source sha, originalFilename, artifact sha, mapping sidecar |

## Bằng chứng code paths cần xác minh (v0.1.0)

- `js/ifc/ifc-adapter.js`: `processEntity`, `carveItemOpenings`, `meshForMappedItem`, `meshForBooleanClippingResult`, `detectLengthScale`.
- `js/fds/fds-exporter.js`: `strategyForElement`, geometry serialization/GEOM, fallback, source comments.
- `js/app-controller.js`: clip display vs export options.
- `js/compare/checks.js`: checks hiện có và giới hạn.
- `js/workers/`: phân biệt bundle inline và worker source.

## Triaging chuẩn cho agent

Mỗi finding cần: `id`, `status`, `affectedVersions`, `reproducer`, `sourceFileSha`, `expected`, `actual`, `rootCause`, `fixCommit`, `tests`, `residualRisks`, `reviewer`.

Các nhãn trong report: `CONFIRMED_IN_SNAPSHOT`, `REPRODUCED_ON_HEAD`, `ALREADY_FIXED`, `NOT_REPRODUCIBLE`, `BLOCKED`. Không tự dùng mô tả audit cũ làm kết quả test hiện hành.

## Những điều chưa được chứng minh

- Không có FDS B1/B2 hiện hành trong ZIP để đo đầy đủ HVAC/PCCC thực tế.
- Không có benchmark ngang hàng giữa IFCtoFDS/BFDS/IfcOpenShell custom exporter cùng dataset và machine.
- Không có xác minh FDS official solver cho tất cả testcase.
