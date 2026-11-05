# P1 — Retention nhất quán sau restart bằng timestamp SQLite

**Ngày:** 05/11/2026. **Finding:** `IO-RETENTION-01` từ `FULL_REASSESSMENT_2026_11_05.md`.

## Nguyên nhân

Trước sửa, `JobService.touch()` đã commit `last_accessed` vào SQLite trước khi trả HTTP, nhưng `cleanup_orphaned_directories()` (được gọi lúc khởi động) đánh giá thời hạn lưu trữ bằng `Path.stat().st_mtime` của thư mục job. Đọc artifact không nhất thiết làm đổi mtime thư mục. Sau một restart, một artifact vẫn còn hạn theo SQLite có thể bị xóa cùng metadata.

Điều này mâu thuẫn với vòng scheduler bình thường, vốn đã dùng `max(finished, last_accessed)`.

## Invariant mới

- Đối với registered job, startup cleanup chỉ dùng các timestamp `created/finished/last_accessed` đã lưu SQLite; không dùng directory mtime làm nguồn chân lý.
- Không xóa `QUEUED`/`RUNNING` ở pha retention trước khi startup reconciliation hoàn tất.
- `durable=True` luôn được giữ.
- Nếu không có timestamp hợp lệ, không tự ý xóa dữ liệu.
- Chỉ xóa artifact sau khi SQLite delete commit thành công.
- Unregistered job directories giữ nguyên chính sách opt-in manual prune hiện có.
- Không thay đổi các quyết định khoa học, schema result hay FDS output.

`tests/test_job_startup_retention_clock.py`: recent SQLite access + old mtime, expired SQLite timestamp + fresh mtime, crashed RUNNING job và durable job.

## Giới hạn

Bản sửa giải quyết bất đồng startup-retention. Chưa chứng minh streaming download không đụng cleanup, crash giữa DELETE row và remove artifact hoặc nhiều host dùng chung filesystem. G05/G06 vẫn chưa PASS; cần CI đầy đủ và fault injection production sau này.
