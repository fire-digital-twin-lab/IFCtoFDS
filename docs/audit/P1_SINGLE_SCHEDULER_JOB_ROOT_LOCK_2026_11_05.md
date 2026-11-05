# P1 — Khóa độc quyền JobService theo job root

Ngày: 05/11/2026. Phạm vi: triển khai một node/host với SQLite và
filesystem jobs chia sẻ, không phải distributed queue.

## Nguyên nhân

Khóa `threading.RLock` chỉ có tác dụng bên trong **một** tiến trình
Python. Khi cấu hình nhiều worker Uvicorn/process trên cùng `IFCFDS_JOB_ROOT`,
các JobService độc lập có thể cùng đọc QUEUED, spawn job trùng, tranh
SQLite và xóa tệp của nhau.

## Biện pháp fail-closed

- `ExclusiveJobRootLock` giữ một OS lock trên `.scheduler.lock`:
  `fcntl.flock(LOCK_EX | LOCK_NB)` trên Unix,
  `msvcrt.locking(LK_NBLCK)` trên Windows.
- Chế độ `IFCFDS_ENV=staging` hoặc `production` bắt buộc lấy khóa
  trước khi nạp JobRepository và reconcile jobs.
- Process thứ hai không lấy được lock sẽ từ chối khởi tạo JobService;
  không tự xóa lock file để tránh split-brain qua inode mới.
- Lock được giữ suốt vòng đời, chỉ nhả sau khi scheduler thread thực sự
  đã dừng. Nếu thread còn sống sau join, không nhả khóa.
- Nếu mở SQLite hoặc startup reconcile thất bại, nhả lock để một lần
  khởi động hợp lệ có thể tiếp tục.
- Local/test mode giữ nguyên khả năng tạo JobService riêng cho fixture
  và không tự nhận bảo đảm multi-process.

## Regression cần CI trên HEAD

`tests/test_job_root_exclusive_lock.py` kiểm thử:
1. Lấy khóa lần hai trong cùng process bị từ chối.
2. Staging/production từ chối JobService thứ hai trên cùng job root.
3. Đóng service giải phóng khóa và cho phép khởi tạo lại.
4. Khởi tạo SQLite lỗi không giữ khóa mồ côi.
5. Subprocess độc lập bị từ chối khi chủ lock sống, nhận lại được sau release.

## Giới hạn nghiệm thu

- Lock OS trên **một host**; không xác minh NFS/SMB hoặc các loại
  filesystem/network chia sẻ có semantics lock khác nhau.
- Không phải leader election, distributed lease, fencing token,
  Postgres job queue hay exactly-once execution. Chưa hỗ trợ nhiều
  replica ghi chung SQLite; kiến trúc production phải giữ **một**
  scheduler writer hoặc chuyển JobService sang hệ thống điều phối
  phân tán có hợp đồng riêng.
- File lock không bảo vệ trường hợp worker ngoài quy trình không
  tôn trọng khóa hoặc tiến trình bị kill nhưng subprocess còn chạy.
- Vẫn cần process supervision, health/alert, crash tests, rollback,
  storage failure và scientific verification.
- G06 vẫn **INCONCLUSIVE**, không được tự nâng lên PASS từ unit tests.
