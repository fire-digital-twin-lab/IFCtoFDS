# P1 — Hủy job phải được SQLite xác nhận trước khi công bố trạng thái

Ngày: 05/11/2026.

## Triệu chứng và nguyên nhân

`JobService.cancel()` cập nhật trực tiếp đối tượng job trong cache trước khi
gọi `JobRepository.set()`. `set()` cho phép lỗi ghi SQLite bị ghi log rồi
bỏ qua. Vì vậy API có thể công bố `CANCELLED` nhưng SQLite vẫn ghi
`QUEUED`/`RUNNING` sau disk-full/locked SQLite và restart. Worker có thể
bị dừng và source bị dọn trong khi DB chưa phản ánh trạng thái.

## Phạm vi sửa

- Thêm `JobRepository.set_durable()`: `UPDATE` bản ghi đã có, xác nhận
  `rowcount=1`, commit trước khi thay cache; SQLite lỗi phát
  `JobPersistenceError`.
- `JobService.cancel()` dùng bản sao job và chỉ dừng tiến trình, ghi
  diagnostic, dọn source sau khi commit trạng thái hủy.
- API `POST /api/jobs/{jid}/cancel` trả HTTP 503 nếu SQLite lỗi, không
  công bố thành công giả.
- Regression: `tests/test_job_cancel_durability.py` kiểm tra disk-full,
  HTTP 503, RAM/SQLite/source nhất quán và đường hủy thành công.

## Giới hạn và nghiệm thu

Không thay đổi thuật toán IFC/FDS, mapping, solver, hay verdict khoa học.
Không coi `COMPLETED` là `MAPPING_VERIFIED`/`SIMULATION_VERIFIED`.
Finding chỉ **FIXED_PENDING_VERIFICATION** cho đến khi toàn bộ CI trên
HEAD PR thành công. `JobRepository.set()` và các cập nhật trạng thái
khác của scheduler vẫn là nợ persistence riêng cần sửa tiếp, không được
đóng toàn bộ `IO-PERSISTENCE`. Crash/power-loss, multi-process concurrency
và atomicity giữa filesystem/SQLite chưa được chứng minh.
