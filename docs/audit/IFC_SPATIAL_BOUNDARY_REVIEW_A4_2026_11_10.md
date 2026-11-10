# A4.1 — Kiểm kê IfcSpace và IfcRelSpaceBoundary trước khi dựng air-path

**Tình trạng:** Mã ứng viên / phải qua CI, chưa có kết luận hình học, hệ thống thông gió hoặc scientific V&V.
**Nguồn:** IFC được chủ sở hữu cấp quyền. Không đưa IFC công trình và tệp JSON review chứa GUID lên public GitHub.
**Kiến trúc:** Python Verified Core, đọc relationship IFC với IfcOpenShell, không dựng OpenCASCADE hoặc tự tính airflow.

## 1. Root cause và giới hạn thực tế

- IFC hầm thực tế có IfcSpace nhưng thiếu IfcRelSpaceBoundary theo kiểm kê STEP trước đây; spatial relation thiếu không chứng minh tường/cửa vật lý không tồn tại.
- Quan hệ IfcRelSpaceBoundary xác định phần tử ranh giới liên hệ với không gian, không chứng minh tính kín khí, trạng thái cửa, airflow passage, HVAC, áp suất hay tính phù hợp CFD.
- IFC2X3 và IFC4 có khả năng ghi boundary khác nhau; trong IFC4 CorrespondingBoundary chỉ là metadata về cặp boundary, không phải lỗ thông khí đã xác minh.
- `validation/checkers/air_path.py` hiện kiểm soát hình học air-path từ mesh FDS/CSG; preflight này **không thay thế** checker đó và không thay kết quả gate.

## 2. Thực thi riêng tư

`python -m ifc_to_fds spatial-boundary-review "<private-model>.ifc" -o ".local-reference-cases/spatial-review.json"`

Lệnh dùng exclusive-create; file 0600 trên POSIX, Windows phải kiểm soát ACL NTFS. Trường JSON `space_review_queue` có GUID/STEP ID để kỹ sư mở đúng cấu kiện trong BIM viewer, **không** gửi JSON lên GitHub/issue/chat công khai.

Tool đếm IfcSpace, IfcRelSpaceBoundary (bao gồm subtype khi được IfcOpenShell trả về), liên kết RelatingSpace/RelatedBuildingElement, PhysicalOrVirtualBoundary, InternalOrExternalBoundary, CorrespondingBoundary có trong dữ liệu nguồn, thiếu host/boundary và source SHA-256. Tệp nguồn được hash lại sau parse; nếu thay đổi thì từ chối report.

Không dùng tên phòng, không suy ra adjacency từ cùng tầng, không dùng IfcRelConnectsPathElements cho luồng khói, không gán OPEN/CLOSED từ filling relation hoặc boundary.

## 3. Gate và output

Mỗi space: `human_review_status=UNREVIEWED`, `space_geometry_status=NOT_EVALUATED`, `airflow_connectivity=NOT_EVALUATED`.

Tổng file: `spatial_adjacency_verdict=NOT_EVALUATED`, `airflow_verdict=NOT_EVALUATED`, `geometry_verdict=NOT_EVALUATED`, `mapping_verdict=NOT_EVALUATED`, `solver_verdict=NOT_RUN`, `scientific_verdict=INCONCLUSIVE`, `review_approval=NOT_GRANTED`.

**No data is not PASS:** IfcSpace có nhưng không có IfcRelSpaceBoundary → cảnh báo `IFC_SPACE_BOUNDARY_RELATIONS_ABSENT`, giữ nguyên queue để human reviewer kiểm tra. Nếu không có IfcSpace, ghi `NO_IFC_SPACES_IN_SOURCE`, không tự tạo không gian CFD.

## 4. Kiểm thử bắt buộc

- Unit: 2 IfcSpace, physical/virtual boundaries, host, related element, enum, stable output.
- Negative: thiếu toàn bộ boundary, orphan RelatingSpace, thiếu RelatedBuildingElement, duplicated STEP IDs, invalid source hash, không suy luận air-path từ CorrespondingBoundary.
- Integration: public IFC4 fixture thật trong CI qua IfcOpenShell và CLI; không có space → không bịa room/adjacency.
- Privacy: file exclusive-create, no overwrite, 0600 POSIX, stdout không log private IFC source.
- Required workflow: Source Quality, Conversion Correctness Linux/Windows/solver/JS/browser, Production Container, Release Image Security PASS trên HEAD cuối; main push CI sau merge.
- Real IFC: chỉ chạy offline/private runner; chủ dự án/engineer đối chiếu với drawing/MEP/fan schedule/door state, chứ không đưa source file vào CI.

## 5. Phần việc chưa làm — A4.2/A5

Không có nguồn boundary hoặc review → **không** tự dựng graph. A4.2 cần mô hình hình học khoang thực từ IFC/OCC, lỗ thông xuyên tường/sàn và bản vẽ đã duyệt, với độ kín/sai số so independent geometry oracle. A5 cần đo effective geometry sau lưới FDS, kiểm tra những lỗ bị snap mất và kiểm định free-space connectivity độc lập với converter (tránh common-mode verification).

A4.1 là source-evidence prep, **không phải completion của toàn bộ A4/A5** và không đủ tiêu chuẩn để sinh dữ liệu AI nhiệt–khói đã được validation.

**Rollback:** revert 4 tệp, không đổi schema job DB, FDS text, mapping authority, solver hoặc input IFC.
