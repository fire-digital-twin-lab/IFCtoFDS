# P1 — Scheduler tiếp tục hoạt động khi ghi terminal diagnostic gặp lỗi I/O

**Ngày:** 07/11/2026. **Finding:** `IO-SCHEDULER-DIAGNOSTIC-01`. **Trạng thái:** `FIXED_PENDING_VERIFICATION`.

## Lỗi xác định từ đường điều khiển

`JobService._loop()` gọi `_terminal_diagnostic()` trước một số chuyển trạng thái như queue timeout, mất process handle và worker result lỗi. `Path.write_text()` có thể ném `OSError` (ví dụ quyền ghi, filesystem tạm unavailable). Exception thoát khỏi thread `_loop`, khiến scheduler dừng trong khi SQLite còn job QUEUED/RUNNING; readiness và queue có thể ngừng phục vụ.

## Bản sửa và bất biến

- Tách vòng chạy thành `_loop()` (supervisor wrapper) và `_run_loop_until_io_failure()` (vòng nghiệp vụ hiện hành, không đổi thứ tự transition).
- Wrapper chỉ bắt `OSError`, ghi `ERROR` và retry với backoff 0,1–5 giây, không bắt ngoại lệ logic/lập trình khác.
- Không thay đổi kết quả terminal khi diagnostic chưa được ghi; SQLite và input giữ nguyên để thử lại.
- Không thay đổi FDS mapping, hợp đồng scientific verdict, API schema hoặc tolerance.

## Regression

`tests/test_job_scheduler_diagnostic_io.py`: 3 kịch bản thật qua `_loop()`, với lỗi ghi diagnostic lần đầu và phục hồi lần sau:
1. QUEUED quá hạn;
2. RUNNING mất worker handle;
3. RUNNING worker có `result.json` không hợp lệ.

Mỗi ca xác nhận SQLite và IFC nguồn chưa đổi tại thời điểm lỗi, retry thực hiện transition hợp lệ, file nguồn chỉ được dọn sau commit, log lỗi có dấu vết.

## Chưa được nghiệm thu

- Chưa có local pytest trong môi trường này: container không truy cập GitHub DNS để clone.
- Chỉ nâng `VERIFIED` sau khi Python matrix/quality CI PASS trên HEAD, merge không bypass và CI trên merge SHA.
- Chưa giải quyết filesystem crash giữa SQLite và file operations, lỗi I/O liên tục, queue starvation, multi-instance, independent scientific V&V.
- G05/G06 và production vẫn **chưa PASS**.
