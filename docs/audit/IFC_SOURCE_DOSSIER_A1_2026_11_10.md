# A1 — Source Dossier cho IFC công trình thực (chỉ kiểm kê, không dựng geometry)

**Trạng thái:** đề xuất kiểm thử / PR; không phải xác nhận mapping, nghiệm thu khoa học hoặc production.
**Mục tiêu:** preflight IFC2X3/IFC4 trước khi dùng IfcOpenShell/OpenCASCADE để dựng các BREP lớn.
**Phạm vi dữ liệu:** IFC riêng tư **không** được đưa vào git, CI, artifact công khai hoặc log.

## Lệnh sử dụng

Chạy trên máy được ủy quyền đã cài Python 3.12 và ứng dụng:

`python -m ifc_to_fds source-dossier "<path-private-model>.ifc" -o ".local-reference-cases/source-dossier.json"`

Trên Windows PowerShell dùng các đường dẫn Windows tùy máy. `.local-reference-cases/` được gitignore. Không dùng lệnh `inventory --json` với IFC thật để gửi kết quả lên CI vì nó có thể bao gồm tên/path/GlobalId.

Lệnh mới chỉ mở IFC và duyệt class/relationship, **không** gọi `ifcopenshell.geom.create_shape`, boolean, mesh, `FDS`, solver hoặc auto-rebase. JSON được tạo bằng exclusive create (không ghi đè). Trên POSIX, cố tạo quyền file `0600`; trên Windows, operator phải kiểm tra NTFS ACL và thư mục lưu.

Kết quả mặc định chỉ chứa source SHA-256, size, IFC schema, unit conversion, counts theo class, cao độ tầng khai báo, số phần tử trực tiếp, opening/void/fill, các lớp host/fill, số quan hệ trùng/hỏng, warning codes. Không có tên dự án, GlobalId, tên/người thiết kế, filename, path hoặc site/world coordinates trong JSON.

SHA được kiểm tra **trước và sau** khi IfcOpenShell parse để phát hiện thay đổi file nguồn trong lúc xử lý. Source hash là provenance, **không** phải chữ ký số hoặc source-model approval.

## Ngữ nghĩa được khóa

- `IfcRelVoidsElement` có/không `IfcRelFillsElement` **không đủ** suy trạng thái vật lý OPEN/CLOSED; opening không fill là `REVIEW_REQUIRED`.
- `IfcRelConnectsPathElements` không đại diện đường khói thông thoáng.
- Thiếu `IfcFan`/`IfcDuctSegment` trong **tệp này** không chứng minh công trình không có hệ MEP ở model khác.
- `IfcBuildingStorey.Elevation` là thuộc tính khai báo, **không** phải cao độ hình học từ placement matrix, không được coi là world elevation đã xác minh.
- Đếm `IfcSpace` gắn storey qua containment/decomposition chỉ là thống kê quan hệ, **không** phải adjacency, phòng cháy hoặc CFD volume.
- Code không xác minh tọa độ WORLD/REBASED, geometry, GEOM/OBST/VENT, lỗ mở hiệu dụng, solver, nguồn cháy, science.
- Kết luận không thay đổi: `approval_status=DRAFT`, `geometry_verdict=NOT_EVALUATED`, `mapping_verdict=NOT_EVALUATED`, `solver_verdict=NOT_RUN`, `scientific_verdict=INCONCLUSIVE`.

## Acceptance & failure matrix

| Test | Oracle / kết quả bắt buộc |
|---|---|
| Công trình có 2 tầng và unit mm | length scale được tính đúng, không giả định mét |
| Opening và filling | đếm chính xác từng quan hệ; không âm thầm biến void không fill thành OPEN |
| Rel trùng, thiếu host/opening/fill | mã warning rõ, mapping không PASS |
| Missing boundary và MEP | cảnh báo scope, không tự sinh airflow graph |
| SHA nguồn | phát hiện file thay đổi trong quá trình đọc |
| Determinism | cùng IFC bytes -> JSON có thể tái lập; thứ tự floor/class ổn định |
| Privacy | không có entity names, GUID, file path/site coordinate trong output |
| CLI | output phải là file JSON chưa tồn tại; không ghi đè; stdout không in đường dẫn nguồn |
| Integration | chạy với IFC fixture công khai, bằng IfcOpenShell thật trong GitHub CI |
| Research IFC riêng | chỉ chạy local trên máy được ủy quyền; so sánh source-dossier với kiểm kê STEP độc lập, không upload model |

Nếu `IfcRelFillsElement` gắn vào opening không có void, hoặc geometry relationships bất thường, phải đánh dấu warning, đưa vào bước A3; **không** tự tạo FDS HOLE/OBST để khắc phục.

## Dependency & bước tiếp theo

- **A0:** xem main workflow conclusions và complete check contexts trước khi merge; chưa có bằng chứng có thể rerun failed jobs của các run cũ.
- **A2:** kiểm tra site/building/storey placements bằng matrix 4×4, meta unit, chọn local coordinate extraction có double-rebase negative tests.
- **A3:** phân loại riêng các opening host/fill, reviewer queue, missing relations; cần kiểm định FDS effective geometry.
- **A4/A5:** independent CAD/section/drawing reference, boundary/air-path và solver snap evidence.
- **A6:** CPU/peak RSS benchmark với IFC riêng tư, không public artifact.

**Rollback:** revert A1 nếu CI lỗi; không sửa DB, không thay serializer/validation authority, không thay input IFC. Giữ scientific verdict `INCONCLUSIVE`, release `NOT_PRODUCTION_READY`.
