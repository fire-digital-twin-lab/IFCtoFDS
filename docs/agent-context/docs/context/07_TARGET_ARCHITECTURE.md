# 07 — Kiến trúc đích: Hybrid Verified IFC-to-FDS

## Quyết định kiến trúc

Fork **ProfRino/IFCtoFDS** được giữ làm ứng dụng Web/legacy. Dùng **IfcOpenShell Python** như dependency lõi IFC/geometry, không fork IfcOpenShell. Tự phát triển source inventory, canonical schema, MEP system graph, mapping policy và validator độc lập. Dùng BFDS+Bonsai làm đối chứng; Voxelization Toolkit như tùy chọn, FD-Gen không nằm trong scope.

```text
              +-------------------------------+
              | IFC sources: immutable + SHA  |
              +-------------------------------+
                              |
                  Python IFC Ingestion
         (IfcOpenShell geometry + relationships)
                              |
        Federation: units/coords/source identities
                              |
      +---------------- Canonical BIM ----------------+
      | geometry | semantic | openings | MEP graph   |
      +-----------------------------------------------+
                         |             |
                   Scope policy   Mapping policy
                         +------+------+
                                |
                 FDS representations/manifest
                                |
              Serialize actual .fds / metadata
                                |
         +-----------+----------+-------------+
         |           |                        |
       Parser   Independent geometry      HVAC/PCCC
      validity   source-vs-target audit    coverage QA
         +-----------+----------+-------------+
                                |
                ACCEPTED / REJECTED / BLOCKED
                                |
                      Web review UI + CLI
```

## Các cổng ranh giới (module contracts)

1. `SourceIngestion`: IFC(s) → inventories, model transform, shape records, parse warnings.
2. `CanonicalStore`: versioned schema + geometry sidecars; source IDs và schema validation.
3. `ScopeResolver`: explicit scope + source geo → per-object decision.
4. `MEPGraphBuilder`: IFC system/port relations → graph có chứng cứ.
5. `MappingPlanner`: objects → `MapDecision`, reason/cost/geometry tolerances.
6. `FDSExporter`: quyết định đã duyệt → string `.fds` + primitive table; không tự lấy quyết định semantic khi serialize.
7. `IndependentAuditor`: đọc IFC gốc + `.fds` + manifest + config, tái dựng assertions; không trust chính mesh object của exporter.
8. `AcceptanceGate`: quy tắc trên outcomes; xuất acceptance JSON/HTML; không chỉnh sửa findings.
9. `WebBridge`: API run/progress/artifact/finding; quick mode bảo toàn.

## Quyết định lưu trữ

- CLI/offline đầu tiên; không bắt buộc DB/server/network.
- V1 dùng artifact immutable theo `run-id`, JSON versioned cho metadata và hình học tách sidecar nhị phân nếu cần.
- FastAPI cục bộ phục vụ UI Verified phase sau. Không dùng JS trong browser tự gọi Python process; server/API dùng môi trường cô lập.
- Tùy chọn caching bằng source hash + settings + algorithm version, không reuse kết quả cho source/config khác.
- FDS `.fds` là output sinh được từ config; manifest/report là artifact bắt buộc ngang hàng, không thêm chú thích chưa chuẩn cú pháp vào FDS trừ comment hợp lệ.

## Hình học chuẩn và đường validation độc lập

Canonical geometry là chuẩn *conversion*, nhưng independent validator cần dựng reference từ IFC một cách độc lập về thuật toán đo/đối chiếu (ít nhất re-open nguồn, reparse output, đối chứng topology/voxel/golden fixtures). Không dùng duy nhất cùng mesh sau xử lý để tự so với chính nó.

## Duy trì tương thích

- Quick mode: legacy browser JS và file:// (trong giới hạn dependency gốc).
- Verified mode: Python CLI / local API; minh bạch yêu cầu cài Python/IfcOpenShell.
- Worker bundles sinh lại, tests dùng parity.
- Transition theo adapter thay vì `git mv` toàn bộ JS code ngay khi bắt đầu.

## Những ADR bắt buộc viết khi code

`ADR-001 geometry authority`, `ADR-002 canonical contract & binary payload`, `ADR-003 export strategy priorities`, `ADR-004 scope semantics`, `ADR-005 validation independence`, `ADR-006 MEP preservation-vs-function`, `ADR-007 FastAPI/offline/security`, `ADR-008 geometry error policy`.
