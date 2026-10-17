# 13 — Phương pháp kiểm toán độc lập và tiêu chí định lượng

## Ba tầng validation

- **V1 IFC→Canonical:** kiểm chứng parsing/inventory, units, transforms, geometry, openings, MEP source graph.
- **V2 Canonical→Serialized FDS:** parser output, primitive counts, fds source IDs, geometry/tessellation/approximations, topology.
- **V3 Effective FDS:** xét ảnh hưởng mesh/snap/GEOM semantics, bít lỗ mở/đường khí, solver warnings nếu có environment.

Không chỉ đối chiếu object nội bộ của exporter với chính nó. Audit cần re-open IFC nguồn + reparse `.fds`, dùng phép kiểm hình học/geometry reconstruction và các golden fixtures độc lập.

## Metrics và denominator

| Metric | Định nghĩa | Cảnh báo |
|---|---|---|
| `inventory_coverage` | `N_accounted_source / N_in_scope_source` | Tập nguồn phải được định nghĩa và query độc lập |
| `geometry_mapping_coverage` | `N_required_geometry_validly_mapped / N_required_geometry` | SEMANTIC_ONLY không tính success geometry |
| `HVAC/PCCC source coverage` | accounted required MEP / MEP in source | Có thể 100% dù FDS không có chức năng vật lý |
| `connection_precision` | true explicit target edges / predicted explicit edges | Không xem proximity là ground truth |
| `connection_recall` | reproduced explicit edges / source explicit edges | Nguồn IFC thiếu edges không đủ để suy luận physical connectivity |
| `volumetric IoU` | volume(intersection)/volume(union) | Chỉ tính solid/watertight/evaluable geometry |
| `surface deviation` | khoảng cách bề mặt/tập điểm (Hausdorff hoặc sampled) | Sampling/tolerance/units phải ghi |
| `opening preservation` | preserved required openings / required IFC openings | Kiểm tra cả diện tích, thông khí/topology sau mesh |
| `source traceability` | FDS primitives with supported source/derived references / all mapped primitives | Synthetic phải khai báo rõ |
| `solver validity` | parser/static/solver statuses riêng | `NOT_RUN` ≠ `PASS` |

## Tolerance profile (không áp ngưỡng universal)

`epsilon_position_m`, `epsilon_bbox_m`, `epsilon_surface_m`, `epsilon_opening_m`, `epsilon_volume_ratio`, `epsilon_area_ratio`, `min_effective_opening_cells`, `voxel_cell_size_m`, `fds_mesh_dx_m`. Nhóm khoa học phê duyệt tùy chức năng cấu kiện, mesh, mục tiêu nghiên cứu **trước** benchmark.

## Quality checks bắt buộc

- Shape validity: degenerate triangle, self-intersection (khi cần), manifold/watertight/orientation, disconnected comps, boolean errors.
- Coordinate consistency: axis, elevation, unit, multi-model origin, transform reversible.
- Openings/topology: không lấp cửa, lỗ hút xả, shafts; kiểm tra đường liên thông.
- MEP graph: segments, fittings, terminal continuity, source port edges preserved; không tạo false positive.
- FDS namelist: parse lại syntax, unique IDs, references, geometry primitives, positive dimensions, mesh containment, file hash.
- Effective geometry: FDS cell effects ở các lỗ hẹp/đường khí quan trọng; rasterization independent check.

## Mutation tests (kiểm thử năng lực kiểm toán)

1. Xóa một `OBST/GEOM` của tường → `MISSING`.
2. Dời cao độ cột 0.2 m (mức minh họa cho fixture) → `DEVIATED`.
3. Bịt một opening/thay đổi kích thước → `BLOCKED_AIR_PATH`.
4. Hoán đổi source GlobalId → `TRACEABILITY_BROKEN`.
5. Cắt đoạn ống giữa hai fitting → connectivity mismatch nếu quan hệ nguồn explicit.
6. Đổi hệ thống duct thành FP → semantic-system error.
7. Thay run config nhưng tái sử dụng cache cũ → cache invalidation detection.

## Acceptance status

- `MATCHED`: đạt tiêu chí cụ thể trên tập được kiểm chứng.
- `DEVIATED`: có sai lệch > threshold hoặc semantic mismatch.
- `MISSING`: required element không có target hợp lệ.
- `SEMANTIC_ONLY`: preserved metadata nhưng không có FDS geometry.
- `EXCLUDED_APPROVED`: ngoài scope/giản lược được phê duyệt.
- `UNSUPPORTED`: tool chưa hỗ trợ.
- `INCONCLUSIVE`: chưa đủ dữ liệu/đo/solver để kết luận.
- `MISSING_SOURCE_DATA`: yêu cầu case không có dữ liệu nguồn; không tự tạo.

Mọi run chỉ `ACCEPTED` khi các tiêu chí bắt buộc có evidence, P0/P1 = 0 trong scope, các trạng thái unresolved không bị ngụy trang. Solver check về hình học cần phân biệt với FDS fire simulation full-duration.
