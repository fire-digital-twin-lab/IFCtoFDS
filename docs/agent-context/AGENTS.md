# AGENTS.md — Hướng dẫn bắt buộc cho Coding Agent

## Sứ mệnh

Xây công cụ ánh xạ **đúng, đủ, có thể truy vết và kiểm chứng** từ một/nhiều IFC sang hình học FDS; đặc biệt chú trọng kết cấu, hệ thống thông gió (HVAC), hệ thống PCCC. Đây là phần mềm nghiên cứu tiền xử lý hình học, **chưa phải** hệ thống mô phỏng cháy/sprinkler/thiết bị hoàn chỉnh.

## Đọc trước khi thao tác

- `README.md` của bộ context; `docs/context/00_PROJECT_BRIEF.md` đến `25_DELIVERABLES.md` theo thứ tự cần thiết.
- `docs/MASTER_PROMPT_IFCtoFDS_IfcOpenShell_End_to_End.md`.
- Mã nguồn, LICENSE, CITATION, README, tests, docs, worker build scripts của repository đang chạy.

## Các lệnh cấm

- Không giả định “xuất `.fds` thành công” = “đúng hình học”, không tự đánh dấu `VERIFIED` khi thiếu audit.
- Không tự sinh cấu kiện IFC nguồn thiếu, không tạo port/connectivity giả, không suy ra airflow/fan curve/sprinkler/CO device physics.
- Không sửa/đổi tên nội dung IFC gốc. Giữ original filename + checksum; không xóa những đối tượng khó mà không ghi reason/status.
- Không dùng bbox làm thay thế hình học phức tạp mà không đo và phê duyệt sai số; không fallback `GEOM` bị mất lỗ mở.
- Không dùng viewer clip như export scope. Không coi một `IFC_SOURCE` comment là chứng minh hình học tương đương.
- Không `reset --hard`, `clean -fdx`, force-push, thay đổi `main`, merge PR không có phê duyệt; không xóa công việc tồn tại.
- Không dừng ở pseudocode nếu đang được giao triển khai; cũng không claim đã code/test khi chưa chạy.

## Quy trình tối thiểu mỗi lần làm việc

1. `git status --short`, branch, HEAD, remote, tags và dependency versions; xác nhận quyền truy cập.
2. Baseline tests + ghi run log. Nếu phát hiện lỗi, viết fixture/reproducer trước khi sửa.
3. Lập plan PR nhỏ, module ownership, acceptance criteria; chọn giai đoạn phù hợp.
4. Triển khai vertical slice có thể chạy, chạy unit/integration/regression; tái sinh inline workers nếu sửa source tương ứng.
5. Re-parse FDS sau serialize, kiểm tra manifest/source count, kiểm tra geometry và mở/đóng khí.
6. Báo cáo `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN` riêng; không gộp thành “tất cả pass”.
7. Đưa báo cáo SHA/branch/files/tests/findings/risks; chuẩn bị PR, không tự merge.

## Hợp đồng chất lượng

- Inventory: ghi nhận 100% **đối tượng thuộc tập kiểm kê quy định** và giải trình trạng thái; KHÔNG yêu cầu 100% biến thành OBST/GEOM.
- Hình học: fidelity theo dung sai được phê duyệt, không tự đặt ngưỡng 1 mm/5% cho mọi bài toán.
- HVAC/PCCC: phân biệt `SOURCE_EXISTS`, `SEMANTIC_PRESERVED`, `GEOMETRY_MAPPED`, `FUNCTIONALLY_MODELED`.
- Người dùng có thể chọn scope tổng quát; không hardcode B1/B2.
- Independent audit đọc **lại IFC nguồn** và **file FDS đã serialize**, không chỉ tin cùng object model với exporter.
- Human-in-the-loop cho `UNSUPPORTED/INCONCLUSIVE/DEVIATED`.
- Giấy phép fork AGPL-3.0 và notices nguồn phải được giữ; dependency theo license gốc.

## Cấu trúc hai chế độ

- `Quick Conversion`: bản legacy, preview, không gắn nhãn verified.
- `Verified Conversion`: Python IfcOpenShell + canonical model + mapping policies + independent validation + acceptance gate; chỉ báo `VERIFIED` nếu đạt.

## Khi không có dữ liệu / môi trường

- Thiếu IFC/FDS thực tế: tạo fixtures kiểm chứng, báo `BLOCKED: REAL_PROJECT_DATA_UNAVAILABLE` cho acceptance case thực tế.
- Thiếu FDS executable: thực hiện static/parsing/geometry audits và báo `SOLVER_NOT_RUN`, không ghi `SOLVER_PASS`.
- Thiếu tính năng IfcOpenShell / phiên bản không hỗ trợ: phát hiện capability, đánh dấu unsupported có bằng chứng, không bịa kết quả.
- Có yêu cầu xung đột: ưu tiên quyết định mới nhất và nêu chính xác xung đột trong ADR/report.
