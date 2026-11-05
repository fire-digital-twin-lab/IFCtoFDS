# P1 — WAL durability audit: SQLite NORMAL versus FULL

**Ngày kiểm tra:** 05/11/2026. **Finding:** `IO-POWER-01`.  
**Repository:** `ifc_to_fds/adapters/jobs/repository.py`.  
**Mức:** P1, production blocker khi hợp đồng tuyên bố commit-first phải bền vững qua OS crash hoặc mất điện.

## Vấn đề đã xác minh

Trước sửa, cả `_get_connection()` và `_init_db()` đều dùng
`PRAGMA synchronous=NORMAL` trên SQLite `journal_mode=WAL`.
Với NORMAL, SQLite cam kết tính nhất quán và atomicity nhưng các
giao dịch đã commit **có thể bị rollback** nếu hệ điều hành crash hoặc
thiết bị mất nguồn, do không fsync WAL sau mỗi commit.

Nguồn chính thức:
- https://www.sqlite.org/pragma.html#pragma_synchronous
- https://www.sqlite.org/wal.html#performance_considerations

Các regression commit-first từ PR #39–#48 giải quyết SQLite write
failure, process restart, queue lifecycle; chúng **không** thay thế
power-loss durability của tầng lưu trữ.

## Thay đổi

- `IFCFDS_ENV=staging` và `production`: bắt buộc WAL
  `PRAGMA synchronous=FULL` trên **từng connection** (và trong init).
- `local/development/test` giữ NORMAL để tương thích và ưu tiên tốc độ
  vòng chạy developer.
- Không cho phép cấu hình upload/browser đổi mức synchronous.
- Test `tests/test_sqlite_production_sync.py` truy vấn PRAGMA thực
  trên Windows/Linux CI và xác nhận chuyển trạng thái job rồi reload.
- Không thay đổi schema, cấu trúc bản ghi, API, evidence hoặc verdict khoa học.

## Giới hạn cần giữ trước khi nghiệm thu production

- FULL tăng fsync/latency, cần benchmark thực tế trên filesystem/đĩa dự kiến.
- Không giải quyết đồng thời SQLite/filesystem artifacts: có thể crash giữa
  commit metadata và ghi hoặc xóa tệp.
- Sức bền thực tế còn tùy VFS, filesystem, bộ lưu trữ, cache điều khiển
  và độ tin cậy của flush; FULL không phải bản sao dự phòng.
- Không chứng minh khả năng chịu mất điện bằng unit test. Cần
  fault-injection/power-off drill, restore checksum, RPO/RTO và giám sát WAL.
- G05, G06, G12 vẫn chưa PASS. Release `NOT_PRODUCTION_READY`.
