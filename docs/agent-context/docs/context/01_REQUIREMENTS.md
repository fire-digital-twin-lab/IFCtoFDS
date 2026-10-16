# 01 — Danh mục yêu cầu đã chốt (requirements catalogue)

**Mức:** MUST = bắt buộc trong phạm vi nghiệm thu; SHOULD = nên có trong kế hoạch; MAY = mở rộng.  
**Yêu cầu → tiêu chí kiểm tra** phải được liên kết trong `24_TRACEABILITY_MATRIX.md`.

| ID | Mức | Yêu cầu / hành vi cần chứng minh |
|---|---|---|
| REQ-001 | MUST | Không ghi đè file IFC/FDS gốc; lưu original filename, source SHA-256 và run identity |
| REQ-002 | MUST | Nhận nhiều IFC; phân biệt nguồn, schema, đơn vị, placement và kiểm tra căn chỉnh mô hình |
| REQ-003 | MUST | Có inventory toàn bộ `IfcProduct` nguồn theo phạm vi, kể cả không có representation; không bỏ sót âm thầm |
| REQ-004 | MUST | Phân nhóm đúng kiến trúc/kết cấu, HVAC, PCCC và đối tượng khác dựa trên dữ liệu IFC chứ không chỉ name substring |
| REQ-005 | MUST | Chuyển đúng geometry: kích thước, vị trí, cao độ, hướng, transformations, Boolean/openings, ramps, stairs, slabs, walls, beams, columns |
| REQ-006 | MUST | Không tạo vật cản sai khiến cửa, shaft, lối thông khí/hút khói bị bít ngoài ý muốn |
| REQ-007 | MUST | Kiểm kê và bảo toàn thông tin ducts, fittings, dampers, fans, terminals và liên hệ hệ thống có trong IFC |
| REQ-008 | MUST | Kiểm kê và bảo toàn pipes FP, fittings, valves, sprinklers, alarms/sensors/thiết bị PCCC có trong IFC |
| REQ-009 | MUST | Trích xuất system memberships/ports/explicit connections (nếu IFC có); không suy diễn thành `EXPLICIT` từ tiếp xúc hình học |
| REQ-010 | MUST | Phân biệt MEP geometry representation, semantic preservation, physical function; không mô phỏng chức năng khi chưa có chính sách |
| REQ-011 | MUST | Scope xuất thực sự áp dụng lên model, hỗ trợ tầng/volume/system/type và cấu kiện giao cắt biên; khác viewer clip |
| REQ-012 | MUST | Mỗi FDS primitive có source keys, mapping policy, reason, transform, and run provenance; hỗ trợ IFC→n FDS elements |
| REQ-013 | MUST | Alias/shared geometry chỉ chấp nhận sau kiểm tra tương đương hình học và transform có ngưỡng thích hợp |
| REQ-014 | MUST | Source IFC, canonical model, FDS serialized và effective FDS geometry có kiểm tra phân lớp; không tự chấm đúng |
| REQ-015 | MUST | Independent validation có findings severity P0–P3, statuses và acceptance gates; không nâng ACCEPTED nếu chưa đủ bằng chứng |
| REQ-016 | MUST | Tạo `.fds`, inventory, system graph, mapping manifest, report sai lệch và phiên bản/cấu hình chạy |
| REQ-017 | MUST | Giữ chức năng legacy/quick conversion hoạt động; không phá viewer/inline workers hồi quy |
| REQ-018 | MUST | CLI có thể chạy không có UI; Web Verified chạy qua backend/API khi tích hợp, lỗi/progress rõ ràng |
| REQ-019 | MUST | Có test fixtures + regression cho lỗi hình học và tính đầy đủ MEP; báo PASS/FAIL/NOT_RUN/BLOCKED thật |
| REQ-020 | MUST | Tuân thủ AGPL upstream, giấy phép dependency, citations/attribution và quản lý Git/PR an toàn |
| REQ-021 | MUST | Không hardcode B1/B2 hoặc loại công trình; chính sách áp dụng cho các IFC khác |
| REQ-022 | MUST | Định nghĩa và lưu dung sai theo cấu kiện, mesh resolution và mục tiêu nghiên cứu; không dùng ngưỡng duy nhất tùy tiện |
| REQ-023 | SHOULD | Human review cho DEVIATED/UNSUPPORTED/INCONCLUSIVE, lưu quyết định và người/nguồn phê duyệt |
| REQ-024 | SHOULD | Hiển thị overlay IFC/FDS, source tree, filters, error highlights và provenance theo phần tử |
| REQ-025 | SHOULD | Hỗ trợ dataset lớn bằng caching, streaming/chunked geometry, giới hạn bộ nhớ và benchmark |
| REQ-026 | SHOULD | Tách quick/verified, khác nhau về cấp độ bằng chứng và thông báo UI |
| REQ-027 | MAY | Tích hợp voxel toolkit, IfcTester/IDS, BFDS benchmark và Smokeview evidence khi cần |

## Trường hợp người dùng đã nêu rõ

- Chọn chỉ mô phỏng **tầng hầm**, bỏ phần vỉa hè phía trước, tầng 1 và chi tiết không cần thiết trong trường hợp cụ thể; nhưng phải giữ cấu kiện định nghĩa trần/tường/lỗ mở/ram của hầm.
- Giữ nguyên tên tệp nguồn và dấu vết cấu kiện để biết đâu là sàn/dầm/ống gió/ống FP.
- Kiểm tra đầy đủ các ống phòng cháy chữa cháy (FP), ống thông gió và các bộ phận đi kèm.
- Chỉ ánh xạ hình học và hệ thống hiện có **trước khi** tạo kịch bản cháy.
- Review nhiều vòng, phải phát hiện sai lệch và có bằng chứng, không chỉ dựa vào việc nhìn hình.

## Chính sách “100%”

`Inventory accounted coverage = 100%` là đích tính toàn vẹn cho **tập phần tử đã định nghĩa**; không có nghĩa mọi `IfcProduct` phải biến thành vật cản. `Geometry completeness = 100%` là mục tiêu đối với tập **bắt buộc phải xuất hình học**, sau khi áp dụng loại trừ có phê duyệt; không tự nhận đạt nếu chưa test. `HVAC_FUNCTIONAL_READINESS` không đồng nghĩa với `HVAC_GEOMETRY_COVERAGE`.
