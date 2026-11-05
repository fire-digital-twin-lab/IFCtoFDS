# P1 — Ghi trạng thái worker terminal trước khi dọn đầu vào

Ngày: 05/11/2026. Phạm vi chỉ là nhánh `proc.poll() is not None`
trong `JobService._loop`, không thay đổi thuật toán IFC, FDS hay nghiệm thu khoa học.

## Nguyên nhân gốc

Nhánh hoàn tất worker thay đổi dictionary cache bằng `running.update()`,
sau đó gọi `_cleanup(running)` xoá `source-*.ifc`, cuối cùng
`repository.set()` ghi SQLite theo best-effort. Khi SQLite lỗi,
metadata bền vững vẫn RUNNING, nhưng cache có thể COMPLETED/FAILED và
file đầu vào đã bị xóa.

## Thay đổi và kiểm thử

- Tạo bản sao `terminal = dict(running)` để không publish trạng thái
  trong RAM trước commit.
- Gọi `JobRepository.set_durable()` với UPDATE + commit trước cleanup;
  `JobPersistenceError` được ghi log và giữ worker terminal để scheduler
  thử lại ở vòng kế tiếp.
- Khi commit thành công, dọn source và request theo chính sách hiện có.
- `tests/test_job_terminal_durability.py` giả lập disk-full, kiểm tra
  RAM/SQLite/source giữ nguyên, sau đó phục hồi DB và chạy lại một vòng
  scheduler để xác nhận trạng thái FAILED và cleanup.

## Điều kiện nghiệm thu và giới hạn

**FIXED_PENDING_VERIFICATION** đến khi CI trên HEAD của PR PASS.
Không kết luận đã xử lý queue-timeout, resource-exhaustion, process
spawn failure, startup-recovery, multi-instance writers, hoặc crash
trong khoảng giữa SQLite commit và filesystem cleanup.
Không cấp `MAPPING_VERIFIED` hay `SIMULATION_VERIFIED` từ job status.
