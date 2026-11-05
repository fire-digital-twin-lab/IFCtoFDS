# P1 — Durable worker startup before subprocess creation

Ngày: 05/11/2026. PR phát sinh từ phát hiện IO-PERSISTENCE / scheduler spawn transition.

## Trước khi sửa

Ở `JobService._loop()`, scheduler gọi `subprocess.Popen`, cập nhật
`QUEUED → RUNNING` trên dictionary dùng chung rồi gọi
`JobRepository.set()` (best-effort). Khi SQLite bị khóa hoặc hết dung
lượng, worker đã có thể chạy trong lúc metadata trên đĩa vẫn `QUEUED`.

Nếu `Popen` hoặc ghi SQLite phát sinh exception, nhánh xử lý có thể
công bố `FAILED` trong RAM và cleanup IFC nguồn trước khi trạng thái
được commit.

## Sau khi sửa

1. Tạo snapshot `RUNNING` riêng (chưa có process handle).
2. Ghi `RUNNING` bằng `set_durable` trước khi gọi `Popen`.
3. Khi SQLite không thể commit: giữ `QUEUED` trong RAM/SQLite, giữ
   source và không gọi `Popen`.
4. Sau khi SQLite commit: mới khởi chạy subprocess, ghi process handle
   vào dictionary RAM (không serialise handle vào SQLite).
5. Nếu `Popen` lỗi: tạo snapshot `FAILED`, lưu SQLite trước cleanup.
6. Nếu lưu `FAILED` lại lỗi: giữ `RUNNING` trên cache/đĩa và IFC
   nguồn, lưu nguyên nhân spawn lỗi trong pending-terminal intent để
   retry trên vòng scheduler tiếp theo; không biến lỗi thành
   `WorkerProcessMissingError`.

## Regression evidence cần xác minh

`tests/test_job_spawn_durability.py`:

- SQLite lỗi trước spawn: không gọi Popen, trạng thái và source nguyên vẹn.
- SQLite phục hồi: RUNNING commit trước Popen.
- Popen lỗi: FAILED commit và cleanup.
- SQLite lại lỗi khi FAILED: giữ nguyên trạng thái, sau phục hồi retry
  cùng lý do gốc, không spawn lại hoặc làm mất input trước commit.

Chạy các test liên quan và toàn bộ required checks trên HEAD PR.
Không tự đánh dấu PASS trước khi CI trả kết quả.

## Giới hạn

- SQLite và filesystem không tạo một giao dịch nguyên tử. Crash giữa
  ghi `RUNNING` và `Popen` được xem là job interrupted lúc startup
  và cần được startup reconciliation xử lý, không được tự tuyên bố
  worker đã chạy.
- `_pending_terminal` vẫn là intent trong RAM, không phải durable outbox.
  Nếu mất tiến trình trong lúc lưu `FAILED` thất bại, startup recovery
  có thể trả `FAILED` với lý do restart thay vì nguyên nhân spawn gốc.
- Chưa xác minh nhiều scheduler/process trên chung một SQLite, process
  fencing, distributed locking, power failure, filesystem sync hoặc
  bảo toàn dữ liệu từng byte ở mức hệ điều hành.
- Không thay đổi thuật toán IFC/FDS và các verdict khoa học.
- Không đóng G05/G06. Release vẫn `NOT_PRODUCTION_READY`.
