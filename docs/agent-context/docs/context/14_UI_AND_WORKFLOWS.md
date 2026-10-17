# 14 — Workflow của người dùng và giao diện cần xây dựng

## Người dùng chính

- **BIM/IFC Engineer:** kiểm tra nguồn, hệ tọa độ, các IFC model, geometry và quan hệ.
- **FDS Engineer:** quyết định representation, scope, mesh, xem sơ đồ không gian và vấn đề solver.
- **MEP/PCCC Engineer:** xác nhận loại hệ thống, đường ống, fittings/valves/devices/ports và nối hệ.
- **Technical Auditor / Researcher:** kiểm chứng kết quả và chạy benchmark tái lập.

## Workflow chuẩn (Verified)

1. **Import:** chọn 1/n IFC, xác nhận original filename/size/schema/hash, reports đầu vào.
2. **Federate:** hiển thị nguồn, đơn vị và các transform; yêu cầu user giải quyết misalignment trước convert.
3. **Inventory & Systems:** cây cấu kiện theo file/system/storey/type; xem rõ NoGeometry/UnknownPort.
4. **Scope:** chọn vùng/tầng/hệ, nhận diện cấu kiện ở boundary; preview Included/Excluded/Review.
5. **Mapping Plan:** xem policy theo element types hoặc từng object, geometry strategy, tolerance, assumed exclusions.
6. **Convert:** run có progress/cancel/error/retry; tạo `.fds` và manifest có hash.
7. **Audit:** overlay IFC vs FDS, xem missing/deviated/blocked openings; drill-down GlobalId.
8. **Review:** engineer chấp nhận override/phân công sửa có lý do, tạo lại output/validation.
9. **Export:** tải `.fds`, source inventory, mapping manifest, findings, report, config và run metadata.

## UI layout gợi ý

- Sidebar trái: Source tree + scope + filter by systems/types/status.
- Center: Viewer 3D overlay IFC/FDS, clipping hiển thị (rõ chữ `VISUAL ONLY`), difference color layers.
- Sidebar phải: Selected element (sourceFilename, GUID, STEP, class, storey, system, geometry policy, FDS primitive refs, findings).
- Bottom: jobs/progress, checks pipeline, messages, export.
- Không dùng một badge “PASS” cho toàn run khi mới chỉ hoàn thành parse/export.

## Giao diện chế độ Quick

- Giữ functionality/upstream UI thông thường.
- Gắn `PREVIEW / NOT VERIFIED`; không tạo `acceptance.json` có status ACCEPTED.
- Đổi viewer clip không sửa export scope trừ user cố ý chuyển scope.

## UI Error states

- IFC schema unsupported, units unknown, geometry failures, file too large, permission/backend offline.
- Multi-IFC alignment ambiguous hoặc missing geometry.
- Run canceled: cleanup temp artifacts nhưng không xóa bản output đã publish, ghi canceled event.
- Unsupported MEP element: giữ trong inventory, kèm link source.
- Critical deviation: disable hoặc cảnh báo khi tải dưới nhãn Verified; vẫn có thể cho tải DRAFT khi policy cho phép.

## Security & offline

- Local CLI và local Web API ưu tiên vì IFC công trình có thể nhạy cảm.
- Không tự upload IFC lên cloud khi người dùng chưa yêu cầu.
- Nếu API public, kiểm soát file size, auth, sandbox processing, quotas, file retention, path traversal và command injection.
- Không ghi full IFC metadata cá nhân vào public telemetry; logs tối thiểu để debug.
