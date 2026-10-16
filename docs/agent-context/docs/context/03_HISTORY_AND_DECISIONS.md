# 03 — Lịch sử yêu cầu và quyết định đã chốt

**Chú ý:** tài liệu tóm tắt từ ngữ cảnh các cuộc trao đổi, không phải nhật ký Git hoặc chứng cứ thực nghiệm mới. Các mục mang nhãn `HISTORICAL` cần so với file thật trước khi triển khai.

## Chuỗi yêu cầu theo thời gian

| Thời điểm (2026) | Nhu cầu / diễn tiến | Quyết định duy trì |
|---|---|---|
| 03/10 | Bắt đầu đối chiếu 2 file IFC và FDS; yêu cầu đúng kết cấu, PCCC, thông gió | IFC là nguồn dữ liệu công trình; sửa FDS phải dựa trên đối chiếu |
| 03/10 | Chỉ tập trung hầm, bỏ vỉa hè phía trước, tầng 1 và phần ngoài mô phỏng | Áp dụng scope có kiểm soát; không mất mặt phân cách/ram/lỗ mở |
| 03–05/10 | Người dùng chỉ ra file sau ánh xạ bị đổi tên, thiếu ống; yêu cầu kiểm tra ống FP | Bảo toàn filename/GlobalId/type/system; inventory MEP/PCCC |
| 05/10 | Làm rõ hầm đường bộ so với hầm gửi xe; hỏi kích thước B1/B2, quạt sự cố và CO sensors | Ca lịch sử là hầm công trình B1/B2; chưa chứng minh counts công suất/tọa độ thiết bị nếu thiếu IFC gốc |
| 12/10 | Người dùng đưa MASTER PROMPT audit/validation IFC→FDS dùng được cho mọi công trình | Tiêu chí tổng quát, độc lập với đúng một công trình |
| 12–13/10 | Khảo sát mã nguồn mở IFCtoFDS, IfcOpenShell, BFDS, voxel toolkit, FD-Gen | Fork IFCtoFDS làm nền Web; dùng IfcOpenShell làm lõi, các tool khác phụ trợ/benchmark |
| 15/10 | Đưa ZIP IFCtoFDS v0.1.0, yêu cầu review toàn diện | Xác định nhiều P0/P1 theo yêu cầu nghiên cứu; giữ baseline và sửa theo gates |
| 15–16/10 | Hỏi giải pháp tối ưu và cách tích hợp Python/JS | Hybrid canonical model + policy + independent audit + human review |
| 16/10 | Đã fork repo, yêu cầu master prompt end-to-end | Repo thực tế `fire-digital-twin-lab/IFCtoFDS`, không tự đổi tên |
| 16/10 | Yêu cầu gói toàn bộ ngữ cảnh Markdown cho coding agent | Bộ tài liệu này là input đọc trước khi code |

## Quyết định có hiệu lực

- **D-001:** Thực hiện việc ánh xạ chính xác **trước**, không làm kịch bản cháy.
- **D-002:** Công cụ phải dùng được cho nhiều công trình, không cứng hóa số tầng, tọa độ hoặc tên hệ thống.
- **D-003:** Fork chính `ProfRino/IFCtoFDS`; IfcOpenShell dạng dependency; không fork lõi IfcOpenShell.
- **D-004:** Hai chế độ quick legacy / verified pipeline; source of truth geometry từ IFC đã chuẩn hóa.
- **D-005:** Đầy đủ kết cấu/HVAC/PCCC theo dữ liệu **thực có** trong IFC; metadata và mô phỏng vật lý được phân biệt.
- **D-006:** Chỉ nhận kết quả qua báo cáo kiểm toán có bằng chứng và acceptance gate; lỗi chưa xác định không bị đánh dấu success.
- **D-007:** Không mất định danh/filename nguồn. Phần tử ngoài scope và alias phải có căn cứ.
- **D-008:** Tận dụng lại UI/viewer/exporter hợp lệ; từng PR nhỏ và test hồi quy, không rewrite toàn bộ.
- **D-009:** Có thể dùng nhóm coding agent + audit agent độc lập; audit không được lấy lời giải của coding agent làm chứng cứ duy nhất.

## Ý tưởng chưa là yêu cầu sản phẩm

- Kịch bản cháy xe máy điện, học máy/surrogate, điều khiển quạt/cảm biến, FD-Gen, nhiều mô phỏng FDS là đề tài dài hạn, hiện **không trong scope**.
- Các giải pháp BFDS, Bonsai, Voxelization Toolkit dùng đối chiếu/phụ trợ, không bắt buộc nhúng vào core.
- Số liệu kích thước tầng hầm lịch sử trong `21_BASEMENT_CASE_STUDY.md` chưa được xác thực ở session này và không thể thay IFC nguồn.

## Quy tắc giải quyết xung đột tài liệu

Chỉ đạo rõ ràng mới nhất của người dùng > requirement đã chốt ở file 01–02 > master prompt > khuyến nghị kiến trúc cũ > ý tưởng khám phá/case study lịch sử. Nếu thay đổi requirement, tạo ADR và cập nhật ma trận traceability.
