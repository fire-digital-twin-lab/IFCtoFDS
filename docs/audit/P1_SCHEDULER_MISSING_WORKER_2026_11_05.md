# P1 — Scheduler không được chết khi mất worker handle

**Bằng chứng lỗi:** Workflow `Conversion correctness` trên merge commit
`e5bf71b0`, run
[41882156171](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41882156171),
job Python Ubuntu 3.11: `test_submit_scenario_job_executes_mesh_gate` nhận
`QUEUED` sau 30 giây vì `JobService._loop` truy cập `None.poll()`.
Pytest ghi `PytestUnhandledThreadExceptionWarning` và 1 failed / 536 passed.

**Khắc phục:** Khi một job `RUNNING` không có `process` hoặc thời điểm
bắt đầu, scheduler tạo diagnostic rõ ràng, đưa job về `FAILED`, ghi
SQLite và tiếp tục vòng giám sát. Không có đường nào coi job này là
`COMPLETED` hoặc bằng chứng khoa học đã kiểm định.

**Regression:** `tests/test_job_missing_worker.py` điều khiển chính
vòng `_loop()` một lượt, tạo job RUNNING thiếu process, đối chiếu cache,
SQLite và diagnostic; tránh timer flaky trong ca kiểm này.

**Trạng thái:** FIXED_PENDING_VERIFICATION. CI trên commit sửa mới cần
hoàn thành trước merge; phép chạy FDS trên dữ liệu công trình thật vẫn
NOT_RUN. Đây chưa giải quyết toàn bộ race condition hoặc persistence.
