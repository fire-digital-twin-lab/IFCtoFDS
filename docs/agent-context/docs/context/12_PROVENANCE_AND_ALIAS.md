# 12 — Truy vết IFC↔FDS, định danh, alias và nguồn dữ liệu

## Provenance chain

```text
source_file (immutable bytes + sha256)
  -> IFC product (GlobalId/STEP ID/IfcClass/Name/Tag/System)
  -> Geometry representation(s) + transforms + openings
  -> Scope and mapping decision (policy version + reason)
  -> FDS primitive(s) and/or semantic-only sidecar
  -> Serialized .fds (hash)
  -> Independent validation finding(s)
  -> Human review/acceptance decision
```

Mỗi con trỏ phải mở rộng được từ UI và CLI. Tên file `.fds` do tool tạo **không được** làm mất `originalFilename` của IFC nguồn.

## IFC và FDS quan hệ nhiều-nhiều

- 1 IFC wall có thể → nhiều `OBST` (voxel decomposition) + `HOLE`.
- 1 component `GEOM` có thể là hợp thành nhiều IFC elements chỉ nếu quyết định hợp nhất được ghi và có policy; nếu không, không gộp mất tính truy vết.
- Một phần tử IFC chỉ có semantic không có FDS primitive thì phải có status `SEMANTIC_ONLY` chứ không bị thiếu âm thầm.
- Một `FDS_ID` mới có thể được cấp để tránh trùng, nhưng mapping phải khôi phục được GlobalId/type/name/system.

## Alias policy

Không dùng bbox/centroid/kích thước xấp xỉ giống nhau làm điều kiện đủ. Muốn tạo geometry alias:

1. So sánh canonical geometry (với units/placement đã normalize).
2. Xem topology, openings, mesh/BRep equality trong error bound và inverse transforms.
3. Chốt source element identity vẫn riêng biệt; alias chỉ dùng lại geometry payload, không gộp semantic objects.
4. Ghi `aliasGroup`, `canonicalShapeHash`, `transform`, `maxDeviation`, `validationEvidence`, `approval`.
5. Alias không đạt hoặc không đủ evidence → giữ geometry riêng hoặc `INCONCLUSIVE`.

## Phân biệt dạng provenance

- `EXPLICIT_IFC`: trực tiếp từ IFC source.
- `ALGORITHM_DERIVED`: thay đổi hình học/đơn giản hóa có thuật toán, sai số và version.
- `HUMAN_REVIEWED`: đã có quyết định con người, ghi reviewer/time/rationale.
- `UNKNOWN_SOURCE`: source thiếu/chưa xác định, không nên VERIFIED.

## Bảo toàn các file và thời gian chạy

- Tạo artifact subfolder theo `run-id`, không ghi đè kết quả cũ; lưu output/checksum.
- Ghi `IfcOpenShell` version, Python/Node/FDS versions, renderer/exporter versions, commit SHA và parameters.
- Redact thông tin BIM nhạy cảm khỏi Git/log nếu IFC nội bộ; không tự push model private vào public repo.
- Giữ original filename + source type/name trong inspector và manifest, không đổi tên thuộc tính nguồn vì UI muốn đẹp.
