# 11 — Nhiều IFC, federation và xuất phạm vi nghiên cứu

## Federation một hoặc nhiều nguồn

1. Xác định SHA-256, IFC schema, schema version, file identifiers và original names.
2. Kiểm tra IfcUnitAssignment, model origin, axis orientation, ObjectPlacement, map conversion/georeferencing khi tồn tại.
3. Chọn common project coordinate frame, sử dụng transform riêng cho từng file, ghi lý do/độ tin cậy.
4. Không tự cộng các tọa độ địa lý rất lớn rồi làm tròn sang float32 cho geometry QA; có thể dùng rebase origin nhưng phải reversible.
5. Kiểm tra xung đột trùng GlobalId giữa file, duplicate geometry/element, semantically overlapping models. Không âm thầm gộp.
6. Nếu không có đủ thông tin xác lập cùng hệ tọa độ, `BLOCKED: COORDINATE_ALIGNMENT_REQUIRED` hoặc yêu cầu user cung cấp control points; không đoán offset chỉ vì bbox gần nhau.

## Export scope khác viewer clip

`ViewerClip`: chỉ ẩn bớt phần render để người dùng kiểm tra.  
`ExportScope`: chính sách quyết định phần nào được đưa vào FDS, phải được giữ trong config/manifest/test.

Scope có thể gồm:

- `storeys[]`, `systems[]`, `ifcTypes[]`, `geometryRegionBox`, `includeIntersectingElements`, `boundaryRetentionPolicy`, `excludedElementKeys[]`.
- `KEEP_WHOLE`, `GEOMETRIC_CLIP_VERIFIED` hoặc `BLOCK_UNSUPPORTED` cho element giao biên.
- Phần tử không được export nếu `EXCLUDED_APPROVED` nhưng vẫn có entry trong source inventory.

## Ví dụ B1/B2 — quy tắc tổng quát

- Người dùng muốn loại phần vỉa hè phía trước, tầng 1, phần không cần thiết để mô phỏng cháy tầng hầm.
- Tuy vậy trần B1 có thể do sàn tầng 1 tạo thành; tầng nền hầm có thể có ramp/cột/shaft vượt biên. Chỉ lọc theo tên tầng là sai.
- Cần giữ slabs, ramp, walls, vertical shafts/penetrations làm ranh giới không gian hầm; các phần đè/trùng từ hai IFC phải đối chiếu.
- Mục tiêu là áp dụng policy tương tự cho *bất kỳ công trình*; không hardcode hai nhãn `B1`, `B2` trong code core.

## Geometry clipping test

- Element hoàn toàn trong scope / ngoài scope / giao cắt boundary.
- Slab trên tầng nghiên cứu nhưng là ceiling boundary của vùng dưới.
- Duct xuyên biên scope, terminal và lỗ xuyên tường.
- Stair/ramp nối 2 tầng; không bị cắt mất mà tạo false closure.
- Vỉa hè ngoài scope không bị export nhưng các đường cấp/hút khí cần giữ không tự bít.

## Yêu cầu xuất

Manifest ghi nguyên scope config + `boundaryRetentionPolicy`, `includedBy`, `excludedBy`, `intersectedAt`, `geometryAfterClippingRef`, `computedBbox`; independent audit so sánh đúng phần hình học clip có phê duyệt chứ không so với toàn element rồi báo sai giả.
