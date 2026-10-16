# 16 — Test matrix, fixture và benchmark khoa học

## Lớp test

1. Unit: units, placement matrices, geometry hash, reason/status mapping, policy precedence.
2. Golden IFC fixtures: kiểu, solids, openings, MappedItem, polygon bounded Boolean, geometry degeneracy.
3. MEP semantic: system/port graph, unknown ports, class variations theo IFC2x3/IFC4.
4. Export: emitted OBST/GEOM/HOLE and source comments, serialized reparse, output consistency.
5. Independent validation: correct acceptance of known fixture and catching seeded faults.
6. Worker/browser: standalone/inline worker parity, viewer overlay, Quick mode compatibility.
7. Integrated CLI/API: end-to-end import/convert/validate/artifact UI.
8. Performance: repeats, stable environment, peak RSS, time each stage, primitive size, FDS parser/solver check.

## Test ID chặn release

| ID | Fixture/action | Expected |
|---|---|---|
| T-01 | IfcOpenShell Duplex | Full inventory nhận được `IFCCOVERING=13`, `IFCFOOTING=7`; không nhầm là exported count |
| T-02 | FZK tường 3 openings | No solidification ở all-GEOM/OBST+HOLE; geometry match có tolerance |
| T-03 | Rotated/mirrored mapped item + mapping origin | world transform đúng theo golden matrix |
| T-04 | SI mm, conversion-based foot | geometry về mét, ghi factor/unit provenance |
| T-05 | `IfcRelConnectsPorts` graph | giữ số edge explicit, đúng endpoints/direction có trong source |
| T-06 | Two ducts spatially touch but no port edge | không tự tạo explicit connection |
| T-07 | Scope B1/B2 crossing boundary | giữ boundary slab/ramp/shaft; viewer clip độc lập scope |
| T-08 | Voxel budget limit | không fallback silent sang GEOM sai |
| T-09 | Browser worker parity | worker inline/regular same FDS/hash theo input cùng version |
| T-10 | Delete OBST/GEOM deliberately | validator flags MISSING/REJECTED |
| T-11 | Narrow vent at coarse FDS cell size | phát hiện effective blocked air path |
| T-12 | Formal FDS parser/solver smoke | log version + actual outcome, NOT_RUN nếu unavailable |
| T-13 | Multi-IFC misaligned frames | BLOCKED trước conversion hoặc guided registration có evidence |
| T-14 | IFC malformed geometry | không crash silent, giữ source inventory & error |
| T-15 | FP/sprinkler graph | complete source systems, no implicit sprinkler actuation |
| T-16 | Opening filling closed vs open | policy explicitly defined, test both states |
| T-17 | Shadow/overlapping sources | duplicate ID and geometry conflict surfaced |
| T-18 | Geometry alias | only reuse verified shapes; semantic identities distinct |

## Benchmark inputs

- Các file mẫu `AC20-FZK-Haus.ifc`, `AC20-Institute-Var-2.ifc`, `IfcOpenShell-Duplex.ifc` đi kèm repo (kiểm tra license và file existence).
- Fixtures mới tối thiểu tự tạo có expected outputs.
- IFC công trình thực tế có hai tầng hầm B1/B2 + HVAC/PCCC, nếu được cung cấp hợp pháp và xác nhận thuộc cùng project. Chưa có trong artifact được phân tích ở đây.

## Cách benchmark không thiên vị

- A: upstream IFCtoFDS v0.1.0/commit khóa.
- B: Bonsai+BFDS bán tự động với kỹ sư, tính cả thời gian làm sạch/chỉnh sửa và loại thao tác.
- C: Verified hybrid mới.
- Cùng IFC, cùng scope, cùng tolerance/mesh (nếu đại diện), cùng OS/runtime/hardware, n lần chạy có warmup và cold start ghi riêng.
- Thống kê median/p95/RSS/number primitives/geometry coverage/opening preservation/connectivity fidelity; không bịa dữ liệu, không suy luận tốc độ từ 1 lần đo.
- Chỉ so sánh `IfcOpenShell parsing` với `legacy parsing` khi input operations tương đương; geometry completeness phải báo kèm performance.

## Tiêu chí scientific reproducibility

- Pin source SHA, source licensing, tool commits, environment, seed/random settings nếu dùng.
- Lưu raw benchmark CSV/JSON, đo theo từng stage (parse, geometrize, graph, scope, FDS serialization, validation).
- Không trình bày benchmark CI tests thành nghiệm thu trên công trình thực nếu thiếu dữ liệu source/engineer review.
