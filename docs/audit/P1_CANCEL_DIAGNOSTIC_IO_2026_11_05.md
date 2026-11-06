# P1 — Không báo hủy thất bại khi diagnostic gặp lỗi I/O sau SQLite commit

**Ngày:** 05/11/2026. **Finding:** `IO-CANCEL-DIAGNOSTIC-01`. **Phân loại:** P1 theo nhánh hủy công việc.

## Nguyên nhân có thể xác minh bằng mã

`JobService.cancel()` gọi `set_durable(... state=CANCELLED)` trước khi ghi `diagnostics.json`.
Nếu `Path.write_text()` phát sinh `OSError` (ví dụ thiếu dung lượng hoặc bị từ chối quyền ghi),
API trước sửa có thể trả HTTP 500 dù SQLite đã ghi `CANCELLED`. Các bước dừng worker
và dọn đầu vào bị bỏ qua vì exception thoát khỏi hàm.

## Thay đổi và invariant

- Sau khi SQLite commit `CANCELLED`, lỗi I/O khi tạo diagnostic được **ghi log ERROR**, nhưng không làm thất bại phản hồi hủy.
- Không nuốt exception của SQLite: `set_durable` vẫn fail-closed như trước.
- Giữ nguyên các bước stop/cleanup và kết quả hủy; không tự đánh dấu conversion hay mô phỏng verified.
- Bản sửa nằm trên nhánh phụ thuộc PR #57 (nonfatal input cleanup), vốn phụ thuộc PR #55 (startup retention).

## Kiểm tra

`tests/test_job_cancel_diagnostic_io.py`: tiêm `PermissionError` và `OSError` vào diagnostic,
đối chiếu trạng thái trả về, SQLite sau reload, cleanup nguồn và log lỗi.

**Tại thời điểm tạo:** `FIXED_PENDING_VERIFICATION`. Chưa có local full test từ môi trường hiện hành;
phải chờ CI hoàn thành trên đúng HEAD, review, merge và xác minh lại `main`.

## Giới hạn

Chưa xử lý tất cả đường viết diagnostic trong scheduler, disk-full trên SQLite,
filesystem crash, retention/download race, hoặc xác minh vật lý FDS.
Các gate G05/G06/G09/G10/G11–G15 vẫn không được nâng lên PASS.
